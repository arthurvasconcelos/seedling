from __future__ import annotations

import asyncio
import importlib
import json
import os
import re
import time
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from seedling._formats import dump_fixture, load_fixture
from seedling.environments import PROD
from seedling.exceptions import CircularDependencyError
from seedling.resolver import topological_sort
from seedling.runner import SeederRunner
from seedling.state import compute_hash, ensure_state_table, get_latest_states

app = typer.Typer(no_args_is_help=True)

# ── Output helpers ────────────────────────────────────────────────────────────


def _err(message: str) -> None:
    Console(stderr=True, highlight=False).print(f"[bold red]✗[/bold red]  {message}")


def _ok(message: str) -> None:
    Console(highlight=False).print(f"[bold green]✓[/bold green]  {message}")


# ── Guards and wiring ─────────────────────────────────────────────────────────


def _check_prod_guard(env: str) -> None:
    if env != PROD:
        return
    if os.environ.get("SEEDLING_ALLOW_PROD") != "1":
        _err("Set SEEDLING_ALLOW_PROD=1 to allow running against production.")
        raise typer.Exit(1)
    Console(highlight=False).print(
        Panel(
            "You are about to seed the [bold]production[/bold] environment.\n"
            "This cannot be undone.",
            title="[yellow]⚠  Production",
            border_style="yellow",
            expand=False,
        )
    )
    typer.confirm("Continue?", abort=True)


def _load_config() -> dict[str, Any]:
    try:
        with open("pyproject.toml", "rb") as f:
            raw: dict[str, Any] = tomllib.load(f).get("tool", {}).get("seedling", {})
            return raw
    except FileNotFoundError:
        _err("No pyproject.toml found. Run from your project root.")
        raise typer.Exit(1) from None


def _get_runner(env: str) -> SeederRunner:
    config = _load_config()

    runner_path = config.get("runner")
    if not runner_path:
        _err(
            "[tool.seedling] runner is not configured in pyproject.toml.\n"
            '  Add: runner = "myapp.seeders:create_runner"'
        )
        raise typer.Exit(1)

    module_path, func_name = runner_path.rsplit(":", 1)
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        _err(f"Could not import {module_path!r}: {exc}")
        raise typer.Exit(1) from exc

    state_tracking: bool = config.get("state_tracking", True)
    create_runner: Callable[[str], SeederRunner] = getattr(module, func_name)
    runner = create_runner(env)
    # Apply config-level state_tracking override if not already set by the factory.
    runner._state_tracking = state_tracking
    return runner


def _resolve_seeders(runner: SeederRunner, names: list[str] | None) -> tuple[Any, ...]:
    if not names:
        return ()
    classes = []
    for name in names:
        try:
            classes.append(runner.get_by_name(name))
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
    return tuple(classes)


def _run_with_progress(coro: Any, label: str, env: str, total: int) -> float:
    """Run *coro* under a Rich progress bar. Returns elapsed seconds."""
    console = Console(highlight=False)
    start = time.perf_counter()
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        TextColumn("[dim]({task.completed}/{task.total})[/dim]"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task_id = progress.add_task(f"Seeding  [dim]{env}[/dim]", total=total)

        def on_finish(name: str) -> None:
            progress.advance(task_id)

        asyncio.run(coro(on_seeder_finish=on_finish))

    return time.perf_counter() - start


# ── Commands ──────────────────────────────────────────────────────────────────


@app.command("run")
def run_cmd(
    seeders: Annotated[list[str] | None, typer.Argument()] = None,
    env: Annotated[
        str, typer.Option("--env", help="Environment to seed")
    ] = "development",
    new_only: Annotated[
        bool,
        typer.Option(
            "--new-only", help="Skip seeders whose hash matches the latest success"
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Re-run all seeders even if state says success"),
    ] = False,
    max_parallel: Annotated[
        int | None,
        typer.Option(
            "--max-parallel", help="Cap concurrency within a dependency level"
        ),
    ] = None,
    tag: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Only run seeders with this tag (repeatable)"),
    ] = None,
) -> None:
    """Run seeders in dependency order."""
    runner = _get_runner(env)
    _check_prod_guard(env)
    if max_parallel is not None:
        runner._max_parallel = max_parallel
    tag_set: set[str] | None = set(tag) if tag else None
    seeder_classes = _resolve_seeders(runner, seeders)
    total = len(runner.list_seeders(*seeder_classes, tags=tag_set))

    import functools

    elapsed = _run_with_progress(
        functools.partial(
            runner.run, *seeder_classes, new_only=new_only, force=force, tags=tag_set
        ),
        label="Seeding",
        env=env,
        total=total,
    )
    _ok(f"Done  [bold]{total}[/bold] seeders  [dim]{elapsed:.2f}s[/dim]")


@app.command("fresh")
def fresh_cmd(
    seeders: Annotated[list[str] | None, typer.Argument()] = None,
    env: Annotated[
        str, typer.Option("--env", help="Environment to seed")
    ] = "development",
    max_parallel: Annotated[
        int | None,
        typer.Option(
            "--max-parallel", help="Cap concurrency within a dependency level"
        ),
    ] = None,
    tag: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Only run seeders with this tag (repeatable)"),
    ] = None,
) -> None:
    """Truncate affected tables then run seeders."""
    runner = _get_runner(env)
    _check_prod_guard(env)
    if max_parallel is not None:
        runner._max_parallel = max_parallel
    tag_set: set[str] | None = set(tag) if tag else None
    seeder_classes = _resolve_seeders(runner, seeders)
    total = len(runner.list_seeders(*seeder_classes, tags=tag_set))

    import functools

    elapsed = _run_with_progress(
        functools.partial(runner.fresh, *seeder_classes, tags=tag_set),
        label="Seeding",
        env=env,
        total=total,
    )
    _ok(f"Done  [bold]{total}[/bold] seeders  [dim]{elapsed:.2f}s[/dim]")


@app.command("export")
def export_cmd(
    seeders: Annotated[list[str] | None, typer.Argument()] = None,
    env: Annotated[
        str, typer.Option("--env", help="Environment to seed")
    ] = "development",
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output file (.json or .yaml/.yml)",
        ),
    ] = Path("fixtures.json"),
) -> None:
    """Export seeded rows to a fixture file (JSON or YAML)."""
    runner = _get_runner(env)
    seeder_classes = _resolve_seeders(runner, seeders)
    data = asyncio.run(runner.export(*seeder_classes))
    if not data:
        _err(
            "No models declared on any registered seeder. "
            "Add `models = [MyModel]` to your Seeder classes."
        )
        raise typer.Exit(1)
    try:
        dump_fixture(data, output)
    except ImportError as exc:
        _err(str(exc))
        raise typer.Exit(1) from exc
    total = sum(len(rows) for rows in data.values())
    _ok(
        f"Exported [bold]{total}[/bold] rows across [bold]{len(data)}[/bold] table(s) to [cyan]{output}[/cyan]"
    )


@app.command("restore")
def restore_cmd(
    file: Annotated[
        Path, typer.Argument(help="Fixture file to restore (.json or .yaml/.yml)")
    ],
    env: Annotated[
        str, typer.Option("--env", help="Environment (used to resolve the runner)")
    ] = "development",
) -> None:
    """Restore rows from a fixture file into the database."""
    if not file.exists():
        _err(f"File not found: {file}")
        raise typer.Exit(1)
    try:
        data = load_fixture(file)
    except ImportError as exc:
        _err(str(exc))
        raise typer.Exit(1) from exc
    except (ValueError, Exception) as exc:
        _err(f"Failed to parse fixture file: {exc}")
        raise typer.Exit(1) from exc

    runner = _get_runner(env)
    total = asyncio.run(runner.restore(data))
    _ok(f"Restored [bold]{total}[/bold] rows from [cyan]{file}[/cyan]")


@app.command("list")
def list_cmd(
    seeders: Annotated[list[str] | None, typer.Argument()] = None,
    env: Annotated[
        str, typer.Option("--env", help="Environment to filter by")
    ] = "development",
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Print seeder names only, one per line"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show idempotent flag and models in addition to defaults",
        ),
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output as JSON array")
    ] = False,
    tag: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Filter by tag (repeatable)"),
    ] = None,
) -> None:
    """Print resolved execution order without running anything."""
    runner = _get_runner(env)
    tag_set: set[str] | None = set(tag) if tag else None
    seeder_classes = _resolve_seeders(runner, seeders)
    ordered = runner.list_seeders(*seeder_classes, tags=tag_set)

    if json_output:
        rows = [
            {
                "name": cls.__name__,
                "depends_on": [d.__name__ for d in cls.depends_on],
                "environments": sorted(cls.environments),
            }
            for cls in ordered
        ]
        typer.echo(json.dumps(rows, indent=2))
        return

    if quiet:
        for cls in ordered:
            typer.echo(cls.__name__)
        return

    console = Console(highlight=False)
    console.print(
        f"\n[bold]Execution order[/bold]  "
        f"[dim]{env}[/dim]  "
        f"[dim]{len(ordered)} seeder{'s' if len(ordered) != 1 else ''}[/dim]"
    )

    table = Table(
        box=box.SIMPLE_HEAD, show_header=True, header_style="bold", padding=(0, 1)
    )
    table.add_column("#", style="dim", justify="right", width=4)
    table.add_column("Seeder")
    table.add_column("Environments", style="cyan")
    table.add_column("Depends on", style="dim")
    if verbose:
        table.add_column("Idempotent", justify="center", style="dim")

    for i, cls in enumerate(ordered, 1):
        deps = ", ".join(d.__name__ for d in cls.depends_on) or "—"
        envs = ", ".join(sorted(cls.environments))
        row: list[str] = [str(i), cls.__name__, envs, deps]
        if verbose:
            row.append("✓" if cls.idempotent else "✗")
        table.add_row(*row)

    console.print(table)


@app.command("status")
def status_cmd(
    env: Annotated[
        str, typer.Option("--env", help="Environment to query")
    ] = "development",
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Show the latest run per seeder with drift detection."""
    runner = _get_runner(env)
    ordered = runner.list_seeders()

    if not ordered:
        _err("No seeders registered for this environment.")
        raise typer.Exit(1)

    async def _fetch() -> dict[str, Any]:
        async with runner._session_factory() as session:
            await ensure_state_table(session)
            return await get_latest_states(
                session, [cls.__name__ for cls in ordered], env
            )

    latest = asyncio.run(_fetch())

    if json_output:
        rows = []
        for cls in ordered:
            entry = latest.get(cls.__name__)
            current_hash = compute_hash(cls)
            drift = (
                entry is not None
                and entry.get("content_hash") is not None
                and entry["content_hash"] != current_hash
            )
            rows.append(
                {
                    "name": cls.__name__,
                    "status": entry["status"] if entry else None,
                    "started_at": entry["started_at"].isoformat()
                    if entry and entry["started_at"]
                    else None,
                    "duration_ms": entry["duration_ms"] if entry else None,
                    "drift": drift,
                    "run_id": entry["run_id"] if entry else None,
                }
            )
        typer.echo(json.dumps(rows, indent=2))
        return

    console = Console(highlight=False)
    console.print(f"\n[bold]Seeder status[/bold]  [dim]{env}[/dim]")

    table = Table(
        box=box.SIMPLE_HEAD, show_header=True, header_style="bold", padding=(0, 1)
    )
    table.add_column("Seeder")
    table.add_column("Status", justify="center")
    table.add_column("Last run", style="dim")
    table.add_column("Duration", justify="right", style="dim")
    table.add_column("Drift", justify="center")

    for cls in ordered:
        entry = latest.get(cls.__name__)
        current_hash = compute_hash(cls)

        if entry is None:
            status_str = "[dim]never run[/dim]"
            last_run = "—"
            duration = "—"
            drift_str = "—"
        else:
            status_val = entry["status"]
            if status_val == "success":
                status_str = "[green]success[/green]"
            elif status_val == "error":
                status_str = "[red]error[/red]"
            else:
                status_str = f"[yellow]{status_val}[/yellow]"

            started = entry.get("started_at")
            last_run = started.strftime("%Y-%m-%d %H:%M:%S") if started else "—"
            ms = entry.get("duration_ms")
            duration = f"{ms}ms" if ms is not None else "—"

            has_drift = (
                entry.get("content_hash") is not None
                and entry["content_hash"] != current_hash
            )
            drift_str = "[yellow]⚠ drift[/yellow]" if has_drift else "[dim]—[/dim]"

        table.add_row(cls.__name__, status_str, last_run, duration, drift_str)

    console.print(table)


@app.command("validate")
def validate_cmd(
    env: Annotated[
        str, typer.Option("--env", help="Environment to validate for")
    ] = "development",
) -> None:
    """Static validation: cycles, missing deps, empty environments, missing models."""
    runner = _get_runner(env)

    issues: list[str] = []

    # Cycle detection
    try:
        topological_sort(runner._registry)
    except CircularDependencyError as exc:
        issues.append(f"Circular dependency: {exc}")

    # Missing dependencies
    registered_set = set(runner._registry)
    for cls in runner._registry:
        for dep in cls.depends_on:
            if dep not in registered_set:
                issues.append(
                    f"{cls.__name__}: depends on {dep.__name__!r} which is not registered"
                )

    # Empty environments
    for cls in runner._registry:
        if not cls.environments:
            issues.append(
                f"{cls.__name__}: environments is empty — seeder will never run"
            )

    # Missing models (advisory — not all seeders need models)
    no_models = [cls.__name__ for cls in runner._registry if not cls.models]
    if no_models:
        for name in no_models:
            issues.append(
                f"{name}: models list is empty — seeder won't appear in `seed export`"
            )

    console = Console(highlight=False)
    if issues:
        console.print("\n[bold red]Validation failed[/bold red]\n")
        for issue in issues:
            console.print(f"  [red]✗[/red]  {issue}")
        raise typer.Exit(1)

    console.print(
        f"\n[bold green]✓[/bold green]  All checks passed for env=[cyan]{env}[/cyan]"
    )


@app.command("graph")
def graph_cmd(
    seeders: Annotated[list[str] | None, typer.Argument()] = None,
    env: Annotated[
        str, typer.Option("--env", help="Environment to graph")
    ] = "development",
    mermaid: Annotated[
        bool,
        typer.Option(
            "--mermaid", help="Output Mermaid flowchart instead of Graphviz DOT"
        ),
    ] = False,
) -> None:
    """Output the dependency graph as Graphviz DOT (default) or Mermaid."""
    runner = _get_runner(env)
    seeder_classes = _resolve_seeders(runner, seeders)
    ordered = runner.list_seeders(*seeder_classes)

    if not ordered:
        _err("No seeders registered for this environment.")
        raise typer.Exit(1)

    if mermaid:
        lines = ["flowchart TD"]
        for cls in ordered:
            for dep in cls.depends_on:
                if dep in ordered or not seeder_classes:
                    lines.append(f"    {dep.__name__} --> {cls.__name__}")
        if not any("-->" in line for line in lines):
            for cls in ordered:
                lines.append(f"    {cls.__name__}")
        typer.echo("\n".join(lines))
    else:
        lines = ["digraph seedling {", '    rankdir="LR";']
        for cls in ordered:
            lines.append(f'    "{cls.__name__}";')
        for cls in ordered:
            for dep in cls.depends_on:
                lines.append(f'    "{dep.__name__}" -> "{cls.__name__}";')
        lines.append("}")
        typer.echo("\n".join(lines))


# ── Scaffolding ───────────────────────────────────────────────────────────────


_SEEDERS_INIT = '''\
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from seedling import SeederRunner


def create_runner(env: str) -> SeederRunner:
    """Return a configured SeederRunner for *env*.

    Replace the session factory below with your application's engine/sessionmaker.
    Then register your seeders::

        runner.register(MySeeder)
        # or discover them automatically:
        # runner.discover("seeders")
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///db.sqlite3")
    session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    runner = SeederRunner(session_factory, env=env)
    # runner.register(MySeeder)
    return runner
'''

_FACTORIES_INIT = """\
from __future__ import annotations

# Import your factories here so they are registered in the factory registry.
# Example:
#   from factories.user import UserFactory
"""

_SEEDER_STUB = """\
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from seedling import Seeder
from seedling.environments import DEV_AND_TEST


class {name}(Seeder):
    environments = DEV_AND_TEST
    depends_on = []
    models = []

    async def run(self, session: AsyncSession) -> None:
        pass
"""

_FACTORY_STUB = """\
from __future__ import annotations

from seedling import AutoFactory
from {model_module} import {model_name}


class {factory_name}(AutoFactory[{model_name}]):
    model = {model_name}
{extra_fields}\
"""


def _to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower()


@app.command("init")
def init_cmd() -> None:
    """Scaffold seeders/ and factories/ packages and configure pyproject.toml."""
    cwd = Path.cwd()
    pyproject = cwd / "pyproject.toml"

    if not pyproject.exists():
        _err("No pyproject.toml found. Run from your project root.")
        raise typer.Exit(1)

    created: list[str] = []

    # seeders/
    seeders_dir = cwd / "seeders"
    if not seeders_dir.exists():
        seeders_dir.mkdir()
        (seeders_dir / "__init__.py").write_text(_SEEDERS_INIT)
        created.append("seeders/__init__.py")
    else:
        _ok("seeders/ already exists — skipped")

    # factories/
    factories_dir = cwd / "factories"
    if not factories_dir.exists():
        factories_dir.mkdir()
        (factories_dir / "__init__.py").write_text(_FACTORIES_INIT)
        created.append("factories/__init__.py")
    else:
        _ok("factories/ already exists — skipped")

    # [tool.seedling] in pyproject.toml
    raw = pyproject.read_text()
    if "[tool.seedling]" not in raw:
        raw += '\n[tool.seedling]\nrunner = "seeders:create_runner"\n'
        pyproject.write_text(raw)
        created.append("pyproject.toml [tool.seedling]")
    else:
        _ok("[tool.seedling] already configured — skipped")

    console = Console(highlight=False)
    for item in created:
        console.print(f"  [bold green]created[/bold green]  {item}")
    if created:
        _ok("Done. Edit seeders/__init__.py to wire up your database.")


@app.command("make:seeder")
def make_seeder_cmd(
    name: Annotated[str, typer.Argument(help="Seeder class name, e.g. UserSeeder")],
) -> None:
    """Generate a seeder stub in seeders/<name_snake>.py."""
    if not name[0].isupper():
        _err("Seeder name should be CamelCase, e.g. UserSeeder")
        raise typer.Exit(1)

    seeders_dir = Path.cwd() / "seeders"
    if not seeders_dir.exists():
        _err("seeders/ directory not found. Run `seed init` first.")
        raise typer.Exit(1)

    snake = _to_snake(name)
    dest = seeders_dir / f"{snake}.py"
    if dest.exists():
        _err(f"{dest.relative_to(Path.cwd())} already exists.")
        raise typer.Exit(1)

    dest.write_text(_SEEDER_STUB.format(name=name))
    _ok(f"Created  [cyan]{dest.relative_to(Path.cwd())}[/cyan]")


@app.command("make:factory")
def make_factory_cmd(
    model: Annotated[
        str,
        typer.Argument(
            help="Dotted path to the SQLAlchemy model, e.g. myapp.models:User"
        ),
    ],
) -> None:
    """Generate a factory stub for a SQLAlchemy model."""
    if ":" not in model:
        _err("Provide a dotted path: module:ClassName (e.g. myapp.models:User)")
        raise typer.Exit(1)

    module_path, model_name = model.rsplit(":", 1)
    try:
        mod = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        _err(f"Could not import {module_path!r}: {exc}")
        raise typer.Exit(1) from exc

    model_cls = getattr(mod, model_name, None)
    if model_cls is None:
        _err(f"{model_name!r} not found in {module_path!r}")
        raise typer.Exit(1)

    factories_dir = Path.cwd() / "factories"
    if not factories_dir.exists():
        _err("factories/ directory not found. Run `seed init` first.")
        raise typer.Exit(1)

    snake = _to_snake(model_name)
    dest = factories_dir / f"{snake}.py"
    if dest.exists():
        _err(f"{dest.relative_to(Path.cwd())} already exists.")
        raise typer.Exit(1)

    # Introspect columns to generate explicit field stubs for non-nullable,
    # non-PK, non-FK string columns — useful as a starting point.
    extra_fields = _introspect_factory_fields(model_cls)

    factory_name = f"{model_name}Factory"
    content = _FACTORY_STUB.format(
        model_module=module_path,
        model_name=model_name,
        factory_name=factory_name,
        extra_fields=extra_fields,
    )
    dest.write_text(content)
    _ok(f"Created  [cyan]{dest.relative_to(Path.cwd())}[/cyan]")


def _introspect_factory_fields(model_cls: Any) -> str:
    """Return explicit field assignments for simple string/int columns."""
    try:
        from sqlalchemy import String
        from sqlalchemy import inspect as sa_inspect

        mapper = sa_inspect(model_cls)
        lines: list[str] = []
        for attr in mapper.mapper.column_attrs:
            col = attr.columns[0]
            if col.primary_key or col.foreign_keys:
                continue
            if col.nullable:
                continue
            if isinstance(col.type, String):
                lines.append(f'    {attr.key} = ""  # TODO: set a sensible default')
        return "\n".join(lines) + "\n" if lines else ""
    except Exception:
        return ""

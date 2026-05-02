from __future__ import annotations

import asyncio
import decimal
import importlib
import json
import os
import time
import tomllib
import uuid
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

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
) -> None:
    """Run seeders in dependency order."""
    runner = _get_runner(env)
    _check_prod_guard(env)
    if max_parallel is not None:
        runner._max_parallel = max_parallel
    seeder_classes = _resolve_seeders(runner, seeders)
    total = len(runner.list_seeders(*seeder_classes))

    import functools

    elapsed = _run_with_progress(
        functools.partial(runner.run, *seeder_classes, new_only=new_only, force=force),
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
) -> None:
    """Truncate affected tables then run seeders."""
    runner = _get_runner(env)
    _check_prod_guard(env)
    if max_parallel is not None:
        runner._max_parallel = max_parallel
    seeder_classes = _resolve_seeders(runner, seeders)
    total = len(runner.list_seeders(*seeder_classes))

    import functools

    elapsed = _run_with_progress(
        functools.partial(runner.fresh, *seeder_classes),
        label="Seeding",
        env=env,
        total=total,
    )
    _ok(f"Done  [bold]{total}[/bold] seeders  [dim]{elapsed:.2f}s[/dim]")


class _JsonEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime | date):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return str(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


@app.command("export")
def export_cmd(
    seeders: Annotated[list[str] | None, typer.Argument()] = None,
    env: Annotated[
        str, typer.Option("--env", help="Environment to seed")
    ] = "development",
    output: Annotated[Path, typer.Option("--output", "-o", help="Output file")] = Path(
        "fixtures.json"
    ),
) -> None:
    """Export seeded rows to a JSON fixture file."""
    runner = _get_runner(env)
    seeder_classes = _resolve_seeders(runner, seeders)
    data = asyncio.run(runner.export(*seeder_classes))
    if not data:
        _err(
            "No models declared on any registered seeder. "
            "Add `models = [MyModel]` to your Seeder classes."
        )
        raise typer.Exit(1)
    output.write_text(json.dumps(data, cls=_JsonEncoder, indent=2))
    total = sum(len(rows) for rows in data.values())
    _ok(
        f"Exported [bold]{total}[/bold] rows across [bold]{len(data)}[/bold] table(s) to [cyan]{output}[/cyan]"
    )


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
) -> None:
    """Print resolved execution order without running anything."""
    runner = _get_runner(env)
    seeder_classes = _resolve_seeders(runner, seeders)
    ordered = runner.list_seeders(*seeder_classes)

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

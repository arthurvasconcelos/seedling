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
from seedling.runner import SeederRunner

app = typer.Typer(no_args_is_help=True)

# ── Output helpers ────────────────────────────────────────────────────────────


def _err(message: str) -> None:
    """Print a styled error line to stderr."""
    Console(stderr=True, highlight=False).print(f"[bold red]✗[/bold red]  {message}")


def _ok(message: str) -> None:
    """Print a styled success line to stdout."""
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


def _get_runner(env: str) -> SeederRunner:
    try:
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f).get("tool", {}).get("seedling", {})
    except FileNotFoundError:
        _err("No pyproject.toml found. Run from your project root.")
        raise typer.Exit(1) from None

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

    create_runner: Callable[[str], SeederRunner] = getattr(module, func_name)
    return create_runner(env)


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
) -> None:
    """Run seeders in dependency order."""
    runner = _get_runner(env)
    _check_prod_guard(env)
    seeder_classes = _resolve_seeders(runner, seeders)
    total = len(runner.list_seeders(*seeder_classes))

    import functools

    elapsed = _run_with_progress(
        functools.partial(runner.run, *seeder_classes),
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
) -> None:
    """Truncate affected tables then run seeders."""
    runner = _get_runner(env)
    _check_prod_guard(env)
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
    _ok(f"Exported [bold]{total}[/bold] rows across [bold]{len(data)}[/bold] table(s) to [cyan]{output}[/cyan]")


@app.command("list")
def list_cmd(
    seeders: Annotated[list[str] | None, typer.Argument()] = None,
    env: Annotated[
        str, typer.Option("--env", help="Environment to filter by")
    ] = "development",
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Print seeder names only, one per line")
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show idempotent flag and models in addition to defaults"),
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

    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold", padding=(0, 1))
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

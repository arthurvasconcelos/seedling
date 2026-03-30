from __future__ import annotations

import asyncio
import decimal
import importlib
import json
import tomllib
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from seedling.environments import PROD
from seedling.runner import SeederRunner

app = typer.Typer(no_args_is_help=True)


def _get_runner(env: str) -> SeederRunner:
    try:
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f).get("tool", {}).get("seedling", {})
    except FileNotFoundError:
        typer.echo("Error: no pyproject.toml found. Run from your project root.", err=True)
        raise typer.Exit(1) from None

    runner_path = config.get("runner")
    if not runner_path:
        typer.echo(
            "Error: [tool.seedling] runner is not configured in pyproject.toml.\n"
            "Add: runner = \"myapp.seeders:create_runner\"",
            err=True,
        )
        raise typer.Exit(1)

    module_path, func_name = runner_path.rsplit(":", 1)
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        typer.echo(f"Error: could not import {module_path!r}: {exc}", err=True)
        raise typer.Exit(1) from exc

    create_runner = getattr(module, func_name)
    return create_runner(env)  # type: ignore[no-any-return]


def _resolve_seeders(runner: SeederRunner, names: list[str] | None):
    if not names:
        return ()
    classes = []
    for name in names:
        try:
            classes.append(runner.get_by_name(name))
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
    return tuple(classes)


@app.command("run")
def run_cmd(
    seeders: Annotated[list[str] | None, typer.Argument()] = None,
    env: Annotated[str, typer.Option("--env", help="Environment to seed")] = "development",
) -> None:
    """Run seeders in dependency order."""
    runner = _get_runner(env)
    if env == PROD:
        typer.confirm("Running against production. Continue?", abort=True)
    seeder_classes = _resolve_seeders(runner, seeders)
    asyncio.run(runner.run(*seeder_classes))
    print("Done.")


@app.command("fresh")
def fresh_cmd(
    seeders: Annotated[list[str] | None, typer.Argument()] = None,
    env: Annotated[str, typer.Option("--env", help="Environment to seed")] = "development",
) -> None:
    """Truncate affected tables then run seeders."""
    runner = _get_runner(env)
    if env == PROD:
        typer.confirm("Running against production. Continue?", abort=True)
    seeder_classes = _resolve_seeders(runner, seeders)
    asyncio.run(runner.fresh(*seeder_classes))
    print("Done.")


class _JsonEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return str(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


@app.command("export")
def export_cmd(
    seeders: Annotated[list[str] | None, typer.Argument()] = None,
    env: Annotated[str, typer.Option("--env", help="Environment to seed")] = "development",
    output: Annotated[Path, typer.Option("--output", "-o", help="Output file")] = Path(
        "fixtures.json"
    ),
) -> None:
    """Export seeded rows to a JSON fixture file."""
    runner = _get_runner(env)
    seeder_classes = _resolve_seeders(runner, seeders)
    data = asyncio.run(runner.export(*seeder_classes))
    if not data:
        typer.echo(
            "No models declared on any registered seeder. "
            "Add `models = [MyModel]` to your Seeder classes.",
            err=True,
        )
        raise typer.Exit(1)
    output.write_text(json.dumps(data, cls=_JsonEncoder, indent=2))
    total = sum(len(rows) for rows in data.values())
    print(f"Exported {total} rows across {len(data)} table(s) to {output}")


@app.command("list")
def list_cmd(
    seeders: Annotated[list[str] | None, typer.Argument()] = None,
    env: Annotated[str, typer.Option("--env", help="Environment to filter by")] = "development",
) -> None:
    """Print resolved execution order without running anything."""
    runner = _get_runner(env)
    seeder_classes = _resolve_seeders(runner, seeders)
    ordered = runner.list_seeders(*seeder_classes)
    print(f"Execution order ({len(ordered)} seeders):")
    for i, cls in enumerate(ordered, 1):
        deps = ", ".join(d.__name__ for d in cls.depends_on)
        envs = ", ".join(sorted(cls.environments))
        detail = f"depends_on: {deps}" if deps else f"environments: {envs}"
        print(f"  {i}. {cls.__name__:<35} [{detail}]")

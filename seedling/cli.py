from __future__ import annotations

import asyncio
import importlib
import tomllib
from typing import Annotated

import typer

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
    seeder_classes = _resolve_seeders(runner, seeders)
    asyncio.run(runner.fresh(*seeder_classes))
    print("Done.")


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

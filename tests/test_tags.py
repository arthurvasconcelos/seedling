from __future__ import annotations

from unittest.mock import MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession
from typer.testing import CliRunner

from seedling.cli import app
from seedling.environments import DEV, TEST
from seedling.runner import SeederRunner
from seedling.seeder import Seeder

cli = CliRunner()


# ── Seeder.tags class variable ───────────────────────────────────────────────


def test_seeder_default_tags_is_empty_set():
    class NoTagSeeder(Seeder):
        async def run(self, session: AsyncSession) -> None:
            pass

    assert NoTagSeeder.tags == set()


def test_seeder_tags_declared():
    class DemoSeeder(Seeder):
        tags = {"demo", "smoke"}

        async def run(self, session: AsyncSession) -> None:
            pass

    assert "demo" in DemoSeeder.tags
    assert "smoke" in DemoSeeder.tags


# ── runner.list_seeders tag filtering ────────────────────────────────────────


class SmokeSeeder(Seeder):
    environments = {DEV}
    tags = {"smoke", "demo"}

    async def run(self, session: AsyncSession) -> None:
        pass


class DemoSeeder(Seeder):
    environments = {DEV}
    tags = {"demo"}

    async def run(self, session: AsyncSession) -> None:
        pass


class PlainSeeder(Seeder):
    environments = {DEV}
    tags = set()

    async def run(self, session: AsyncSession) -> None:
        pass


def test_list_seeders_no_tag_filter_returns_all(session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.register(SmokeSeeder, DemoSeeder, PlainSeeder)
    result = runner.list_seeders()
    assert SmokeSeeder in result
    assert DemoSeeder in result
    assert PlainSeeder in result


def test_list_seeders_tag_filter_matches_by_intersection(session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.register(SmokeSeeder, DemoSeeder, PlainSeeder)
    result = runner.list_seeders(tags={"smoke"})
    assert SmokeSeeder in result
    assert DemoSeeder not in result
    assert PlainSeeder not in result


def test_list_seeders_multi_tag_filter_returns_union(session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.register(SmokeSeeder, DemoSeeder, PlainSeeder)
    result = runner.list_seeders(tags={"smoke", "demo"})
    assert SmokeSeeder in result
    assert DemoSeeder in result
    assert PlainSeeder not in result


def test_list_seeders_tag_that_matches_nothing_returns_empty(session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.register(SmokeSeeder, DemoSeeder, PlainSeeder)
    result = runner.list_seeders(tags={"nonexistent"})
    assert result == []


def test_tag_filter_combined_with_env_filter(session_factory):
    class TestOnlySeeder(Seeder):
        environments = {TEST}
        tags = {"smoke"}

        async def run(self, session: AsyncSession) -> None:
            pass

    runner = SeederRunner(session_factory, env=DEV)
    runner.register(SmokeSeeder, TestOnlySeeder)
    result = runner.list_seeders(tags={"smoke"})
    assert SmokeSeeder in result
    assert TestOnlySeeder not in result


# ── runner.run respects tags ─────────────────────────────────────────────────


async def test_run_with_tag_only_runs_matching_seeders(session_factory):
    ran: list[str] = []

    class TaggedA(Seeder):
        environments = {DEV}
        tags = {"smoke"}

        async def run(self, session: AsyncSession) -> None:
            ran.append("A")
            await session.commit()

    class TaggedB(Seeder):
        environments = {DEV}
        tags = {"demo"}

        async def run(self, session: AsyncSession) -> None:
            ran.append("B")
            await session.commit()

    runner = SeederRunner(session_factory, env=DEV, state_tracking=False)
    runner.register(TaggedA, TaggedB)
    await runner.run(tags={"smoke"})
    assert ran == ["A"]


# ── CLI --tag flag ───────────────────────────────────────────────────────────


def _make_pyproject(tmp_path, runner_path="myapp.seeders:create_runner"):
    (tmp_path / "pyproject.toml").write_text(
        f'[tool.seedling]\nrunner = "{runner_path}"\n'
    )


def _make_mock_seeder(name, envs, tags=None):
    mock_cls = MagicMock()
    mock_cls.__name__ = name
    mock_cls.depends_on = []
    mock_cls.environments = set(envs)
    mock_cls.tags = set(tags) if tags else set()
    mock_cls.idempotent = True
    return mock_cls


def test_run_tag_flag_is_passed_to_runner(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = MagicMock()
    mock_runner.list_seeders.return_value = []

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("asyncio.run"):
            cli.invoke(app, ["run", "--tag", "smoke"])

    call_kwargs = mock_runner.list_seeders.call_args
    assert call_kwargs.kwargs.get("tags") == {"smoke"}


def test_list_tag_flag_filters_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    seeder_a = _make_mock_seeder("SmokeSeeder", ["development"], ["smoke"])
    mock_runner = MagicMock()
    mock_runner.list_seeders.return_value = [seeder_a]

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        result = cli.invoke(app, ["list", "--tag", "smoke", "--quiet"])

    assert result.exit_code == 0
    assert "SmokeSeeder" in result.output
    call_kwargs = mock_runner.list_seeders.call_args
    assert call_kwargs.kwargs.get("tags") == {"smoke"}


def test_run_multiple_tags_merged(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = MagicMock()
    mock_runner.list_seeders.return_value = []

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("asyncio.run"):
            cli.invoke(app, ["run", "--tag", "smoke", "--tag", "demo"])

    call_kwargs = mock_runner.list_seeders.call_args
    assert call_kwargs.kwargs.get("tags") == {"smoke", "demo"}

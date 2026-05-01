from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from seedling.cli import app

runner = CliRunner()

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_pyproject(
    tmp_path: Path, runner_path: str = "myapp.seeders:create_runner"
) -> Path:
    """Write a minimal pyproject.toml with [tool.seedling] into tmp_path."""
    content = f'[tool.seedling]\nrunner = "{runner_path}"\n'
    p = tmp_path / "pyproject.toml"
    p.write_text(content)
    return p


def _make_mock_seeder(
    name: str,
    deps: list[str],
    envs: list[str],
    idempotent: bool = True,
) -> MagicMock:
    """Return a mock seeder class with realistic attributes."""
    dep_mocks = [MagicMock(__name__=d) for d in deps]
    mock_cls = MagicMock()
    mock_cls.__name__ = name
    mock_cls.depends_on = dep_mocks
    mock_cls.environments = set(envs)
    mock_cls.idempotent = idempotent
    return mock_cls


def _make_list_runner(seeders: list[MagicMock]) -> MagicMock:
    mock_runner = MagicMock()
    mock_runner.list_seeders.return_value = seeders
    return mock_runner


# ── production guard — run ───────────────────────────────────────────────────


def test_run_prod_fails_without_allow_env_var(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    monkeypatch.delenv("SEEDLING_ALLOW_PROD", raising=False)

    mock_runner = MagicMock()

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        result = runner.invoke(app, ["run", "--env", "production"])

    assert result.exit_code != 0
    assert "SEEDLING_ALLOW_PROD" in result.output


def test_run_prod_aborts_when_user_declines(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    monkeypatch.setenv("SEEDLING_ALLOW_PROD", "1")

    mock_runner = MagicMock()

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        result = runner.invoke(app, ["run", "--env", "production"], input="n\n")

    assert result.exit_code != 0
    assert "production" in result.output.lower() or "continue" in result.output.lower()


def test_run_prod_proceeds_when_env_var_set_and_user_confirms(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    monkeypatch.setenv("SEEDLING_ALLOW_PROD", "1")

    mock_runner = MagicMock()
    mock_runner.list_seeders.return_value = []

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("asyncio.run"):
            result = runner.invoke(app, ["run", "--env", "production"], input="y\n")

    assert "Abort" not in result.output


def test_run_dev_skips_confirmation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = MagicMock()
    mock_runner.list_seeders.return_value = []

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("asyncio.run"):
            result = runner.invoke(app, ["run", "--env", "development"])

    assert "Continue?" not in result.output


# ── production guard — fresh ─────────────────────────────────────────────────


def test_fresh_prod_fails_without_allow_env_var(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    monkeypatch.delenv("SEEDLING_ALLOW_PROD", raising=False)

    mock_runner = MagicMock()

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        result = runner.invoke(app, ["fresh", "--env", "production"])

    assert result.exit_code != 0
    assert "SEEDLING_ALLOW_PROD" in result.output


def test_fresh_prod_aborts_when_user_declines(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    monkeypatch.setenv("SEEDLING_ALLOW_PROD", "1")

    mock_runner = MagicMock()

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        result = runner.invoke(app, ["fresh", "--env", "production"], input="n\n")

    assert result.exit_code != 0


def test_fresh_dev_skips_confirmation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = MagicMock()
    mock_runner.list_seeders.return_value = []

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("asyncio.run"):
            result = runner.invoke(app, ["fresh", "--env", "development"])

    assert "Continue?" not in result.output


# ── missing pyproject.toml ───────────────────────────────────────────────────


def test_run_errors_when_no_pyproject(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0
    assert "pyproject.toml" in result.output


def test_fresh_errors_when_no_pyproject(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["fresh"])
    assert result.exit_code != 0
    assert "pyproject.toml" in result.output


def test_list_errors_when_no_pyproject(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["list"])
    assert result.exit_code != 0
    assert "pyproject.toml" in result.output


# ── export ───────────────────────────────────────────────────────────────────


def test_export_errors_when_no_models_declared(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_seeder_runner = MagicMock()
    mock_seeder_runner._registry = []

    with patch("seedling.cli._get_runner", return_value=mock_seeder_runner):
        with patch("asyncio.run", return_value={}):
            result = runner.invoke(app, ["export"])

    assert result.exit_code != 0
    assert "No models" in result.output


def test_export_writes_fixture_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_seeder_runner = MagicMock()
    mock_seeder_runner._registry = []
    fake_data = {"items": [{"id": 1, "name": "test"}]}

    with patch("seedling.cli._get_runner", return_value=mock_seeder_runner):
        with patch("asyncio.run", return_value=fake_data):
            result = runner.invoke(
                app, ["export", "--output", str(tmp_path / "out.json")]
            )

    assert result.exit_code == 0
    assert "Exported" in result.output
    written = json.loads((tmp_path / "out.json").read_text())
    assert written == fake_data


# ── list flags ───────────────────────────────────────────────────────────────


def test_list_default_shows_rich_table(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    seeder = _make_mock_seeder("UserSeeder", [], ["development"])
    mock_runner = _make_list_runner([seeder])

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "Execution order" in result.output
    assert "UserSeeder" in result.output
    # Table column headers appear in default output
    assert "Seeder" in result.output
    assert "Environments" in result.output


def test_list_quiet_prints_names_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    seeders = [
        _make_mock_seeder("UserSeeder", [], ["development"]),
        _make_mock_seeder("PostSeeder", ["UserSeeder"], ["development"]),
    ]
    mock_runner = _make_list_runner(seeders)

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        result = runner.invoke(app, ["list", "--quiet"])

    assert result.exit_code == 0
    assert "Execution order" not in result.output
    lines = result.output.strip().splitlines()
    assert lines == ["UserSeeder", "PostSeeder"]


def test_list_verbose_shows_idempotent_column(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    seeder = _make_mock_seeder("PostSeeder", ["UserSeeder"], ["development", "test"])
    mock_runner = _make_list_runner([seeder])

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        result = runner.invoke(app, ["list", "--verbose"])

    assert result.exit_code == 0
    assert "PostSeeder" in result.output
    # --verbose adds the Idempotent column
    assert "Idempotent" in result.output


def test_list_json_outputs_valid_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    seeder = _make_mock_seeder("UserSeeder", [], ["development"])
    mock_runner = _make_list_runner([seeder])

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        result = runner.invoke(app, ["list", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert data[0]["name"] == "UserSeeder"
    assert data[0]["depends_on"] == []
    assert "development" in data[0]["environments"]


def test_list_json_includes_dependencies(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    seeder = _make_mock_seeder("PostSeeder", ["UserSeeder"], ["development"])
    mock_runner = _make_list_runner([seeder])

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        result = runner.invoke(app, ["list", "--json"])

    data = json.loads(result.output)
    assert data[0]["depends_on"] == ["UserSeeder"]


# ── run / fresh completion output ────────────────────────────────────────────


def test_run_shows_done_on_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = MagicMock()
    mock_runner.list_seeders.return_value = []

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("asyncio.run"):
            result = runner.invoke(app, ["run"])

    assert result.exit_code == 0
    assert "Done" in result.output


def test_fresh_shows_done_on_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = MagicMock()
    mock_runner.list_seeders.return_value = []

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("asyncio.run"):
            result = runner.invoke(app, ["fresh"])

    assert result.exit_code == 0
    assert "Done" in result.output

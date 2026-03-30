from __future__ import annotations

import tomllib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from seedling.cli import app

runner = CliRunner()

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_pyproject(tmp_path: Path, runner_path: str = "myapp.seeders:create_runner") -> Path:
    """Write a minimal pyproject.toml with [tool.seedling] into tmp_path."""
    content = f'[tool.seedling]\nrunner = "{runner_path}"\n'
    p = tmp_path / "pyproject.toml"
    p.write_text(content)
    return p


# ── production guard — run ───────────────────────────────────────────────────


def test_run_prod_aborts_when_user_declines(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = MagicMock()
    mock_runner.get_by_name.side_effect = ValueError("not used")

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        result = runner.invoke(app, ["run", "--env", "production"], input="n\n")

    assert result.exit_code != 0
    assert "production" in result.output.lower() or "continue" in result.output.lower()


def test_run_prod_proceeds_when_user_confirms(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = MagicMock()
    mock_runner._list_levels.return_value = []

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("asyncio.run"):
            result = runner.invoke(app, ["run", "--env", "production"], input="y\n")

    assert "Abort" not in result.output


def test_run_dev_skips_confirmation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = MagicMock()
    mock_runner._list_levels.return_value = []

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("asyncio.run"):
            result = runner.invoke(app, ["run", "--env", "development"])

    # No confirmation prompt should appear
    assert "Continue?" not in result.output


# ── production guard — fresh ─────────────────────────────────────────────────


def test_fresh_prod_aborts_when_user_declines(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = MagicMock()

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        result = runner.invoke(app, ["fresh", "--env", "production"], input="n\n")

    assert result.exit_code != 0


def test_fresh_dev_skips_confirmation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = MagicMock()
    mock_runner._list_levels.return_value = []

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
            result = runner.invoke(app, ["export", "--output", str(tmp_path / "out.json")])

    assert result.exit_code == 0
    assert "Exported" in result.output
    import json

    written = json.loads((tmp_path / "out.json").read_text())
    assert written == fake_data

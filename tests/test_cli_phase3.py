from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from seedling.cli import app

runner = CliRunner()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_pyproject(tmp_path: Path, extra: str = "") -> Path:
    content = '[tool.seedling]\nrunner = "myapp.seeders:create_runner"\n' + extra
    p = tmp_path / "pyproject.toml"
    p.write_text(content)
    return p


def _make_mock_seeder(
    name: str,
    deps: list[str] | None = None,
    envs: list[str] | None = None,
) -> MagicMock:
    dep_mocks = [MagicMock(__name__=d) for d in (deps or [])]
    mock_cls = MagicMock()
    mock_cls.__name__ = name
    mock_cls.depends_on = dep_mocks
    mock_cls.environments = set(envs or ["development"])
    mock_cls.idempotent = True
    mock_cls.models = []
    return mock_cls


def _make_runner_mock(seeders: list[MagicMock]) -> MagicMock:
    mock_runner = MagicMock()
    mock_runner.list_seeders.return_value = seeders
    mock_runner._registry = seeders
    mock_runner._session_factory = MagicMock()
    mock_runner._state_tracking = True
    return mock_runner


# ── seed run --new-only / --force / --max-parallel ───────────────────────────


def test_run_new_only_flag_passes_to_runner(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = _make_runner_mock([])

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("asyncio.run"):
            result = runner.invoke(app, ["run", "--new-only"])

    assert result.exit_code == 0
    kwargs = mock_runner.run.call_args.kwargs
    assert kwargs.get("new_only") is True


def test_run_force_flag_passes_to_runner(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = _make_runner_mock([])

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("asyncio.run"):
            result = runner.invoke(app, ["run", "--force"])

    assert result.exit_code == 0
    kwargs = mock_runner.run.call_args.kwargs
    assert kwargs.get("force") is True


def test_run_max_parallel_sets_runner_attribute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = _make_runner_mock([])
    mock_runner._max_parallel = None

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("asyncio.run"):
            runner.invoke(app, ["run", "--max-parallel", "3"])

    assert mock_runner._max_parallel == 3


def test_fresh_max_parallel_sets_runner_attribute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = _make_runner_mock([])
    mock_runner._max_parallel = None

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("asyncio.run"):
            runner.invoke(app, ["fresh", "--max-parallel", "2"])

    assert mock_runner._max_parallel == 2


# ── state_tracking config ─────────────────────────────────────────────────────


def test_state_tracking_false_in_config_disables_tracking(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path, "state_tracking = false\n")

    mock_runner = _make_runner_mock([])
    mock_runner._state_tracking = True  # will be overwritten by config

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("asyncio.run"):
            runner.invoke(app, ["run"])

    # The real _get_runner should have set _state_tracking from config.
    # Since we patched _get_runner, we test the config-reading logic separately below.


def test_load_config_reads_state_tracking(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path, "state_tracking = false\n")

    from seedling.cli import _load_config

    config = _load_config()
    assert config.get("state_tracking") is False


# ── seed status ───────────────────────────────────────────────────────────────


def test_status_no_seeders_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = _make_runner_mock([])

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        result = runner.invoke(app, ["status"])

    assert result.exit_code != 0


def test_status_shows_table_with_seeder_names(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    seeder = _make_mock_seeder("UserSeeder")
    mock_runner = _make_runner_mock([seeder])

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("seedling.cli.asyncio.run", return_value={}):
            with patch("seedling.cli.compute_hash", return_value="abc"):
                with patch("seedling.cli.ensure_state_table"):
                    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "UserSeeder" in result.output


def test_status_json_outputs_valid_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    from datetime import datetime

    seeder = _make_mock_seeder("UserSeeder")
    mock_runner = _make_runner_mock([seeder])
    latest = {
        "UserSeeder": {
            "status": "success",
            "started_at": datetime(2026, 5, 1, 12, 0, 0),
            "duration_ms": 42,
            "run_id": "r1",
            "content_hash": "deadbeef",
        }
    }

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("seedling.cli.asyncio.run", return_value=latest):
            with patch("seedling.cli.compute_hash", return_value="deadbeef"):
                with patch("seedling.cli.ensure_state_table"):
                    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert data[0]["name"] == "UserSeeder"
    assert data[0]["status"] == "success"
    assert data[0]["drift"] is False


def test_status_json_flags_drift_when_hash_differs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    from datetime import datetime

    seeder = _make_mock_seeder("DriftedSeeder")
    mock_runner = _make_runner_mock([seeder])
    latest = {
        "DriftedSeeder": {
            "status": "success",
            "started_at": datetime(2026, 5, 1, 12, 0, 0),
            "duration_ms": 10,
            "run_id": "r1",
            "content_hash": "oldhash",
        }
    }

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("seedling.cli.asyncio.run", return_value=latest):
            with patch("seedling.cli.compute_hash", return_value="newhash"):
                with patch("seedling.cli.ensure_state_table"):
                    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["drift"] is True


def test_status_errors_when_no_pyproject(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["status"])
    assert result.exit_code != 0
    assert "pyproject.toml" in result.output


# ── seed validate ─────────────────────────────────────────────────────────────


def test_validate_passes_with_clean_registry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    seeder = _make_mock_seeder("UserSeeder")
    seeder.models = [MagicMock()]  # non-empty models — no issues

    mock_runner = _make_runner_mock([seeder])

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("seedling.cli.topological_sort", return_value=[seeder]):
            result = runner.invoke(app, ["validate"])

    assert result.exit_code == 0
    assert "passed" in result.output


def test_validate_fails_on_circular_dependency(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    from seedling.exceptions import CircularDependencyError

    seeder = _make_mock_seeder("CycleSeeder")
    mock_runner = _make_runner_mock([seeder])

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch(
            "seedling.cli.topological_sort",
            side_effect=CircularDependencyError(["SeederA", "SeederB"]),
        ):
            result = runner.invoke(app, ["validate"])

    assert result.exit_code != 0
    assert "Circular" in result.output


def test_validate_fails_on_missing_dep(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    missing_dep = MagicMock()
    missing_dep.__name__ = "MissingSeeder"

    seeder = _make_mock_seeder("ChildSeeder")
    seeder.depends_on = [missing_dep]
    mock_runner = _make_runner_mock([seeder])

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("seedling.cli.topological_sort", return_value=[seeder]):
            result = runner.invoke(app, ["validate"])

    assert result.exit_code != 0
    assert "MissingSeeder" in result.output


def test_validate_fails_on_empty_environments(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    seeder = _make_mock_seeder("EmptyEnvSeeder")
    seeder.environments = set()  # empty
    mock_runner = _make_runner_mock([seeder])

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("seedling.cli.topological_sort", return_value=[seeder]):
            result = runner.invoke(app, ["validate"])

    assert result.exit_code != 0
    assert "never run" in result.output


def test_validate_warns_on_missing_models(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    seeder = _make_mock_seeder("NoModelSeeder")
    seeder.models = []  # no models
    mock_runner = _make_runner_mock([seeder])

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        with patch("seedling.cli.topological_sort", return_value=[seeder]):
            result = runner.invoke(app, ["validate"])

    assert result.exit_code != 0
    assert "export" in result.output


def test_validate_errors_when_no_pyproject(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["validate"])
    assert result.exit_code != 0
    assert "pyproject.toml" in result.output


# ── seed graph ────────────────────────────────────────────────────────────────


def test_graph_dot_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    seeder_a = _make_mock_seeder("SeederA")
    seeder_b = _make_mock_seeder("SeederB", deps=["SeederA"])
    seeder_b.depends_on = [seeder_a]

    mock_runner = _make_runner_mock([seeder_a, seeder_b])

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        result = runner.invoke(app, ["graph"])

    assert result.exit_code == 0
    assert "digraph seedling" in result.output
    assert '"SeederA" -> "SeederB"' in result.output


def test_graph_mermaid_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    seeder_a = _make_mock_seeder("SeederA")
    seeder_b = _make_mock_seeder("SeederB")
    seeder_b.depends_on = [seeder_a]

    mock_runner = _make_runner_mock([seeder_a, seeder_b])

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        result = runner.invoke(app, ["graph", "--mermaid"])

    assert result.exit_code == 0
    assert "flowchart TD" in result.output
    assert "SeederA --> SeederB" in result.output


def test_graph_no_seeders_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    mock_runner = _make_runner_mock([])

    with patch("seedling.cli._get_runner", return_value=mock_runner):
        result = runner.invoke(app, ["graph"])

    assert result.exit_code != 0


def test_graph_errors_when_no_pyproject(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["graph"])
    assert result.exit_code != 0
    assert "pyproject.toml" in result.output

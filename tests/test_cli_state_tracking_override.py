from __future__ import annotations

import sys
import types

from seedling import SeederRunner
from seedling.cli import _get_runner


def _install_runner_module(monkeypatch, state_tracking: bool) -> None:
    module = types.ModuleType("myapp_seeders")

    def create_runner(env: str) -> SeederRunner:
        return SeederRunner(lambda: None, env=env, state_tracking=state_tracking)  # type: ignore[arg-type]

    module.create_runner = create_runner  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "myapp_seeders", module)


def test_cli_keeps_runner_state_tracking_when_config_silent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.seedling]\nrunner = "myapp_seeders:create_runner"\n'
    )
    _install_runner_module(monkeypatch, state_tracking=False)
    assert _get_runner("development")._state_tracking is False


def test_cli_config_overrides_runner_state_tracking(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.seedling]\nrunner = "myapp_seeders:create_runner"\nstate_tracking = false\n'
    )
    _install_runner_module(monkeypatch, state_tracking=True)
    assert _get_runner("development")._state_tracking is False

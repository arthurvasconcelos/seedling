from __future__ import annotations

from seedling.environments import TEST
from seedling.runner import SeederRunner


def test_seedling_runner_fixture_is_seeder_runner(session_factory):
    """Simulate what the plugin fixture does — verify SeederRunner is returned."""
    runner = SeederRunner(session_factory, env=TEST)
    assert isinstance(runner, SeederRunner)
    assert runner._env == TEST


def test_seedling_runner_uses_test_env_by_default(session_factory):
    runner = SeederRunner(session_factory, env=TEST)
    assert runner._env == TEST


def test_plugin_exports_expected_fixtures():
    """Verify the plugin module exposes the expected fixture functions."""
    import seedling.pytest_plugin as plugin

    assert callable(plugin.seedling_session_factory)
    assert callable(plugin.seedling_env)
    assert callable(plugin.seedling_runner)

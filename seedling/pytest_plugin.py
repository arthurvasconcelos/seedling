"""pytest plugin — provides the ``seedling_runner`` fixture.

Usage in conftest.py::

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    @pytest.fixture(scope="session")
    def seedling_session_factory():
        engine = create_async_engine("postgresql+asyncpg://...")
        return async_sessionmaker(engine, expire_on_commit=False)

Then in tests::

    async def test_seeded(seedling_runner):
        await seedling_runner.run(UserSeeder)
        ...
"""

from __future__ import annotations

import pytest

from seedling.environments import TEST
from seedling.runner import SeederRunner


@pytest.fixture
def seedling_session_factory() -> None:
    """Override this fixture to supply your async_sessionmaker."""
    raise NotImplementedError(
        "Override the 'seedling_session_factory' fixture in your conftest.py "
        "to provide an async_sessionmaker for seedling."
    )


@pytest.fixture
def seedling_env() -> str:
    """Override to change the environment used by seedling_runner (default: 'test')."""
    return TEST


@pytest.fixture
def seedling_runner(seedling_session_factory, seedling_env: str) -> SeederRunner:
    """A SeederRunner bound to the test session factory."""
    return SeederRunner(seedling_session_factory, env=seedling_env)

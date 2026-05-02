"""pytest plugin — provides seedling fixtures and markers.

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

    from seedling.pytest_plugin import seed

    @seed(UserSeeder)
    async def test_with_marker(session): ...

    async def test_with_txn(seedling_transactional_session):
        session = seedling_transactional_session
        ...  # rolled back after test
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest

from seedling.environments import TEST
from seedling.runner import SeederRunner


def seed(*seeder_classes: type) -> pytest.MarkDecorator:
    """Create a ``seed`` mark for the given seeder classes.

    Use this instead of ``@pytest.mark.seed(SomeSeeder)`` to avoid a pytest
    9.x ambiguity where a single callable argument is applied as a decorator
    rather than stored as a mark argument::

        from seedling.pytest_plugin import seed

        @seed(UserSeeder)
        async def test_something(session): ...

        @seed(UserSeeder, PostSeeder)
        async def test_two(session): ...

    ``@pytest.mark.seed([UserSeeder])`` (list form) also works.
    """
    return pytest.mark.seed.with_args(*seeder_classes)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "seed(*seeder_classes): run the given Seeder classes before the test. "
        "Use @seed(...) from seedling.pytest_plugin for cleaner syntax.",
    )


# ── Public fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def seedling_session_factory():
    """Override this fixture in conftest.py to supply an async_sessionmaker.

    Return ``None`` (the default) means seedling fixtures are unconfigured —
    using ``seedling_runner`` or ``@seed(...)`` will raise a clear error.
    """
    return None


@pytest.fixture
def seedling_env() -> str:
    """Override to change the environment used by seedling_runner (default: 'test')."""
    return TEST


@pytest.fixture
def seedling_runner(seedling_session_factory, seedling_env: str) -> SeederRunner:
    """A SeederRunner bound to the test session factory.

    Requires ``seedling_session_factory`` to be overridden in conftest.py.
    """
    if seedling_session_factory is None:
        raise NotImplementedError(
            "Override the 'seedling_session_factory' fixture in your conftest.py "
            "to provide an async_sessionmaker for seedling."
        )
    return SeederRunner(seedling_session_factory, env=seedling_env)


@pytest.fixture
async def seedling_transactional_session(
    seedling_session_factory,
) -> AsyncGenerator:
    """Async session wrapped in a SAVEPOINT that rolls back after the test.

    Use this fixture when you want to seed data and assert against it, but
    leave the database clean for the next test::

        async def test_something(seedling_transactional_session):
            session = seedling_transactional_session
            session.add(MyModel(...))
            await session.flush()
            result = await session.execute(select(MyModel))
            assert result.scalars().first() is not None
        # database is rolled back here — no cleanup needed
    """
    if seedling_session_factory is None:
        raise NotImplementedError(
            "Override the 'seedling_session_factory' fixture in your conftest.py "
            "to provide an async_sessionmaker for seedling."
        )
    async with seedling_session_factory() as session:
        async with session.begin():
            nested = await session.begin_nested()
            try:
                yield session
            finally:
                await nested.rollback()


# ── Internal fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def _seedling_runner_for_marker(
    seedling_session_factory, seedling_env: str
) -> SeederRunner | None:
    """Companion to seedling_runner: returns None instead of raising when unconfigured.

    Declared as an explicit dependency of _seedling_seed_marker so that the
    async fixture chain is resolved BEFORE the marker's async body runs —
    avoiding the 'cannot call Runner.run() from a running event loop' error
    that arises from lazy request.getfixturevalue() inside async fixtures.
    """
    if seedling_session_factory is None:
        return None
    return SeederRunner(seedling_session_factory, env=seedling_env)


@pytest.fixture(autouse=True)
async def _seedling_seed_marker(
    request: pytest.FixtureRequest,
    _seedling_runner_for_marker: SeederRunner | None,
) -> None:
    """Auto-fixture: if the test has @seed / @pytest.mark.seed, run those seeders."""
    marker = request.node.get_closest_marker("seed")
    if marker is None:
        return
    if _seedling_runner_for_marker is None:
        raise pytest.UsageError(
            "To use @seed(), override 'seedling_session_factory' in your conftest.py "
            "to provide an async_sessionmaker for seedling."
        )
    # Support two calling conventions:
    #   @seed(UserSeeder)               → marker.args = (UserSeeder,)
    #   @pytest.mark.seed([UserSeeder]) → marker.args = ([UserSeeder],)
    args = marker.args
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        seeder_classes: tuple[type, ...] = tuple(args[0])
    else:
        seeder_classes = tuple(args)
    await _seedling_runner_for_marker.run(*seeder_classes)

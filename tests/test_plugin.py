from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from seedling.environments import DEV, TEST
from seedling.pytest_plugin import seed
from seedling.runner import SeederRunner
from seedling.seeder import Seeder
from tests.conftest import Item

# ── Basic fixture smoke tests ────────────────────────────────────────────────


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
    assert callable(plugin.seedling_transactional_session)
    assert callable(plugin._seedling_seed_marker)
    assert callable(plugin.seed)


# ── @pytest.mark.seed / @seed() marker ──────────────────────────────────────


class MarkItemSeeder(Seeder):
    environments = {DEV, TEST}
    models = [Item]

    async def run(self, session: AsyncSession) -> None:
        session.add(Item(name="from_seeder", value=42))
        await session.commit()


class MarkItemSeeder2(Seeder):
    environments = {DEV, TEST}
    models = [Item]

    async def run(self, session: AsyncSession) -> None:
        session.add(Item(name="from_seeder_2", value=99))
        await session.commit()


@seed(MarkItemSeeder)
async def test_seed_helper_runs_seeder_before_test(session_factory):
    """@seed(UserSeeder) helper runs the seeder before the test body."""
    async with session_factory() as s:
        rows = (
            (await s.execute(select(Item).where(Item.name == "from_seeder")))
            .scalars()
            .all()
        )
    assert len(rows) >= 1
    assert rows[0].value == 42


@pytest.mark.seed([MarkItemSeeder])
async def test_mark_list_form_runs_seeder(session_factory):
    """@pytest.mark.seed([UserSeeder]) list form also works."""
    async with session_factory() as s:
        rows = (
            (await s.execute(select(Item).where(Item.name == "from_seeder")))
            .scalars()
            .all()
        )
    assert len(rows) >= 1


@seed(MarkItemSeeder, MarkItemSeeder2)
async def test_seed_helper_with_multiple_seeders(session_factory):
    """@seed() with multiple seeders runs all of them."""
    async with session_factory() as s:
        names = {r.name for r in (await s.execute(select(Item))).scalars().all()}
    assert "from_seeder" in names
    assert "from_seeder_2" in names


def test_seed_marker_is_registered_in_pytest(pytestconfig):
    # marker entries look like "seed(*seeder_classes): description" — strip to name
    names = {
        m.split("(")[0].split(":")[0].strip() for m in pytestconfig.getini("markers")
    }
    assert "seed" in names


def test_seed_helper_creates_mark_decorator():

    mark = seed(MarkItemSeeder)
    assert hasattr(mark, "mark")
    assert mark.mark.name == "seed"
    assert MarkItemSeeder in mark.mark.args


def test_seed_list_form_creates_correct_mark():
    mark = pytest.mark.seed([MarkItemSeeder])
    assert mark.mark.name == "seed"
    assert isinstance(mark.mark.args[0], list)
    assert MarkItemSeeder in mark.mark.args[0]


# ── seedling_transactional_session fixture ───────────────────────────────────


async def test_transactional_session_yields_a_session(seedling_transactional_session):
    assert seedling_transactional_session is not None


async def test_transactional_session_can_add_and_flush(seedling_transactional_session):
    session = seedling_transactional_session
    session.add(Item(name="transactional_item", value=7))
    await session.flush()

    result = await session.execute(
        select(Item).where(Item.name == "transactional_item")
    )
    row = result.scalar_one()
    assert row.value == 7


async def test_transactional_session_rolled_back_after_use(session_factory):
    """The SAVEPOINT approach ensures data does not persist outside the fixture."""
    async with session_factory() as session:
        async with session.begin():
            nested = await session.begin_nested()
            try:
                session.add(Item(name="temp_item", value=99))
                await session.flush()
                in_txn = (
                    await session.execute(select(Item).where(Item.name == "temp_item"))
                ).scalar_one()
                assert in_txn.value == 99
            finally:
                await nested.rollback()

    async with session_factory() as check_session:
        after = (
            (await check_session.execute(select(Item).where(Item.name == "temp_item")))
            .scalars()
            .all()
        )
    assert after == []

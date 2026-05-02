from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from seedling.environments import DEV
from seedling.runner import SeederRunner
from seedling.seeder import Seeder
from tests.conftest import Author, Item


class ItemSeeder(Seeder):
    environments = {DEV}
    models = [Item]

    async def run(self, session: AsyncSession) -> None:
        session.add(Item(name="existing", value=10))
        await session.commit()


class AuthorSeeder(Seeder):
    environments = {DEV}
    models = [Author]

    async def run(self, session: AsyncSession) -> None:
        pass


# ── runner.restore() ─────────────────────────────────────────────────────────


async def test_restore_inserts_rows(session_factory) -> None:
    runner = SeederRunner(session_factory, env=DEV, state_tracking=False)
    runner.register(ItemSeeder)

    data = {"items": [{"name": "restored", "value": 99}]}
    total = await runner.restore(data)

    assert total == 1
    async with session_factory() as session:
        rows = (await session.execute(select(Item))).scalars().all()
    assert any(r.name == "restored" and r.value == 99 for r in rows)


async def test_restore_returns_total_row_count(session_factory) -> None:
    runner = SeederRunner(session_factory, env=DEV, state_tracking=False)
    runner.register(ItemSeeder, AuthorSeeder)

    data = {
        "items": [{"name": "a", "value": 1}, {"name": "b", "value": 2}],
        "authors": [{"email": "x@example.com", "first_name": "X"}],
    }
    total = await runner.restore(data)
    assert total == 3


async def test_restore_empty_rows_skipped(session_factory) -> None:
    runner = SeederRunner(session_factory, env=DEV, state_tracking=False)
    runner.register(ItemSeeder)

    total = await runner.restore({"items": []})
    assert total == 0


async def test_restore_unknown_table_is_skipped(session_factory) -> None:
    runner = SeederRunner(session_factory, env=DEV, state_tracking=False)
    runner.register(ItemSeeder)

    # "widgets" is not declared on any seeder — should be a no-op, not a crash
    total = await runner.restore({"widgets": [{"foo": "bar"}]})
    assert total == 0


async def test_restore_empty_fixture_is_a_noop(session_factory) -> None:
    runner = SeederRunner(session_factory, env=DEV, state_tracking=False)
    runner.register(ItemSeeder)

    total = await runner.restore({})
    assert total == 0


async def test_restore_data_is_queryable_after(session_factory) -> None:
    runner = SeederRunner(session_factory, env=DEV, state_tracking=False)
    runner.register(ItemSeeder)

    await runner.restore({"items": [{"name": "queryable", "value": 7}]})

    async with session_factory() as session:
        row = (
            await session.execute(select(Item).where(Item.name == "queryable"))
        ).scalar_one()
    assert row.value == 7


# ── export → restore round-trip ──────────────────────────────────────────────


async def test_export_restore_round_trip(session_factory) -> None:
    runner = SeederRunner(session_factory, env=DEV, state_tracking=False)
    runner.register(ItemSeeder)

    # Seed data via the seeder
    await runner.run(ItemSeeder)

    # Export it
    exported = await runner.export(ItemSeeder)
    assert "items" in exported
    assert len(exported["items"]) == 1

    # Wipe and restore
    async with session_factory() as session:
        await session.execute(Item.__table__.delete())
        await session.commit()

    total = await runner.restore(exported)
    assert total == 1

    async with session_factory() as session:
        rows = (await session.execute(select(Item))).scalars().all()
    assert rows[0].name == "existing"
    assert rows[0].value == 10

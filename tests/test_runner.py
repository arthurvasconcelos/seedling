from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from seedling.environments import DEV, PROD, TEST
from seedling.runner import SeederRunner
from seedling.seeder import Seeder
from tests.conftest import Item

# ── Minimal seeders for testing ─────────────────────────────────────────────────


class ItemSeederA(Seeder):
    environments = {DEV, TEST}

    async def run(self, session: AsyncSession) -> None:
        session.add(Item(name="a", value=1))
        await session.commit()

    async def truncate(self, session: AsyncSession) -> None:
        await session.execute(text("DELETE FROM items WHERE name = 'a'"))


class ItemSeederB(Seeder):
    depends_on = [ItemSeederA]
    environments = {DEV, TEST}

    async def run(self, session: AsyncSession) -> None:
        session.add(Item(name="b", value=2))
        await session.commit()

    async def truncate(self, session: AsyncSession) -> None:
        await session.execute(text("DELETE FROM items WHERE name = 'b'"))


class ProdOnlySeeder(Seeder):
    environments = {PROD}

    async def run(self, session: AsyncSession) -> None:
        session.add(Item(name="prod", value=99))
        await session.commit()


# ── list_seeders ────────────────────────────────────────────────────────────────


def test_list_seeders_returns_all_for_env(session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.register(ItemSeederA, ItemSeederB, ProdOnlySeeder)
    result = runner.list_seeders()
    assert ItemSeederA in result
    assert ItemSeederB in result
    assert ProdOnlySeeder not in result


def test_list_seeders_filters_by_env(session_factory):
    runner = SeederRunner(session_factory, env=PROD)
    runner.register(ItemSeederA, ItemSeederB, ProdOnlySeeder)
    result = runner.list_seeders()
    assert ProdOnlySeeder in result
    assert ItemSeederA not in result


def test_list_seeders_respects_dependency_order(session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.register(ItemSeederA, ItemSeederB)
    result = runner.list_seeders()
    assert result.index(ItemSeederA) < result.index(ItemSeederB)


def test_list_seeders_specific_subset(session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.register(ItemSeederA, ItemSeederB, ProdOnlySeeder)
    result = runner.list_seeders(ItemSeederB)
    assert ItemSeederA in result  # pulled in as dep
    assert ItemSeederB in result
    assert ProdOnlySeeder not in result


# ── get_by_name ─────────────────────────────────────────────────────────────────


def test_get_by_name_returns_class(session_factory):
    runner = SeederRunner(session_factory)
    runner.register(ItemSeederA)
    assert runner.get_by_name("ItemSeederA") is ItemSeederA


def test_get_by_name_raises_for_unknown(session_factory):
    runner = SeederRunner(session_factory)
    with pytest.raises(ValueError, match="Unknown seeder"):
        runner.get_by_name("NonExistent")


# ── register ────────────────────────────────────────────────────────────────────


def test_register_deduplicates(session_factory):
    runner = SeederRunner(session_factory)
    runner.register(ItemSeederA, ItemSeederA)
    assert runner._registry.count(ItemSeederA) == 1


# ── run ─────────────────────────────────────────────────────────────────────────


async def test_run_inserts_rows(engine, session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.register(ItemSeederA, ItemSeederB)
    await runner.run()

    async with session_factory() as s:
        rows = (await s.execute(select(Item))).scalars().all()
    names = {r.name for r in rows}
    assert "a" in names
    assert "b" in names


async def test_run_subset_only_runs_requested(engine, session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.register(ItemSeederA, ItemSeederB)
    await runner.run(ItemSeederA)

    async with session_factory() as s:
        rows = (await s.execute(select(Item))).scalars().all()
    names = {r.name for r in rows}
    assert "a" in names
    assert "b" not in names


# ── fresh ───────────────────────────────────────────────────────────────────────


async def test_fresh_truncates_then_reseeds(engine, session_factory):
    # First run
    runner = SeederRunner(session_factory, env=DEV)
    runner.register(ItemSeederA)
    await runner.run()

    # Run again via fresh — should truncate and re-insert
    await runner.fresh()

    async with session_factory() as s:
        rows = (await s.execute(select(Item))).scalars().all()
    names = [r.name for r in rows]
    # Exactly one 'a' row (not duplicated)
    assert names.count("a") == 1

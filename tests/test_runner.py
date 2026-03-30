from __future__ import annotations

import asyncio

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


# ── parallel execution ──────────────────────────────────────────────────────────


async def test_run_parallel_independent_seeders(engine, session_factory):
    """Seeders with no deps between them should run concurrently (same level)."""
    order: list[str] = []

    class ParallelA(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            await asyncio.sleep(0)  # yield to event loop
            order.append("A")
            session.add(Item(name="pa", value=0))
            await session.commit()

    class ParallelB(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            await asyncio.sleep(0)
            order.append("B")
            session.add(Item(name="pb", value=0))
            await session.commit()

    runner = SeederRunner(session_factory, env=DEV)
    runner.register(ParallelA, ParallelB)
    await runner.run()

    async with session_factory() as s:
        rows = (await s.execute(select(Item))).scalars().all()
    names = {r.name for r in rows}
    assert "pa" in names
    assert "pb" in names
    # Both ran (order doesn't matter for parallel seeders)
    assert set(order) == {"A", "B"}


async def test_run_sequential_dependent_seeders(engine, session_factory):
    """Seeders with a dependency chain must run in strict order."""
    order: list[str] = []

    class SeqA(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            order.append("A")
            session.add(Item(name="sa", value=0))
            await session.commit()

    class SeqB(Seeder):
        depends_on = [SeqA]
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            order.append("B")
            session.add(Item(name="sb", value=0))
            await session.commit()

    runner = SeederRunner(session_factory, env=DEV)
    runner.register(SeqA, SeqB)
    await runner.run()

    assert order == ["A", "B"]


# ── discover ────────────────────────────────────────────────────────────────────


def test_discover_registers_subclasses(session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.discover("tests.fixture_seeders")
    names = {cls.__name__ for cls in runner._registry}
    assert "DiscoverableUserSeeder" in names
    assert "DiscoverablePostSeeder" in names


def test_discover_respects_dependencies(session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.discover("tests.fixture_seeders")
    ordered = runner.list_seeders()
    names = [cls.__name__ for cls in ordered]
    assert names.index("DiscoverableUserSeeder") < names.index("DiscoverablePostSeeder")


def test_discover_deduplicates_on_repeated_calls(session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.discover("tests.fixture_seeders")
    runner.discover("tests.fixture_seeders")
    names = [cls.__name__ for cls in runner._registry]
    assert names.count("DiscoverableUserSeeder") == 1
    assert names.count("DiscoverablePostSeeder") == 1


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

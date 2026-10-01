from __future__ import annotations

import asyncio
import enum

import pytest
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from seedling import AutoFactory, Seeder, SeederRunner, truncate_tables, upsert
from seedling.environments import DEV

from .conftest import Item


class Color(enum.Enum):
    RED = "red"
    GREEN = "green"


class _Base(DeclarativeBase):
    pass


class Paint(_Base):
    __tablename__ = "order"  # reserved word on purpose

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    color: Mapped[Color] = mapped_column(SAEnum(Color))
    size: Mapped[str] = mapped_column(SAEnum("s", "m", "l", name="size_enum"))
    label: Mapped[str] = mapped_column(String(20))


@pytest.fixture
async def paint_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_autofactory_generates_valid_enum_values(paint_session_factory):
    class PaintFactory(AutoFactory[Paint]):
        model = Paint

    async with paint_session_factory() as session:
        rows = await PaintFactory.create_batch(session, 3)
        await session.commit()

    async with paint_session_factory() as session:
        fetched = (await session.execute(select(Paint))).scalars().all()
    assert [r.color for r in rows] == [Color.RED, Color.GREEN, Color.RED]
    assert {r.size for r in fetched} <= {"s", "m", "l"}
    assert len(fetched) == 3


async def test_truncate_tables_quotes_reserved_table_names(paint_session_factory):
    async with paint_session_factory() as session:
        session.add(Paint(color=Color.RED, size="s", label="x"))
        await session.commit()
    async with paint_session_factory() as session:
        await truncate_tables(session, Paint)
        await session.commit()
    async with paint_session_factory() as session:
        assert (await session.execute(select(Paint))).scalars().all() == []


async def test_upsert_rejects_unknown_dialect(session):
    class FakeDialect:
        name = "mssql"

    class FakeConn:
        dialect = FakeDialect()

    async def _connection():
        return FakeConn()

    session.connection = _connection  # type: ignore[method-assign]
    with pytest.raises(NotImplementedError, match="mssql"):
        await upsert(session, Item, {"id": 1, "name": "a"})


async def test_fresh_fires_runner_level_hooks(session_factory):
    events: list[str] = []

    class ItemSeeder(Seeder):
        environments = {DEV}
        models = [Item]

        async def run(self, session: AsyncSession) -> None:
            session.add(Item(name="fresh", value=1))

    class HookedRunner(SeederRunner):
        async def before_run(self, run_id: str, env: str) -> None:
            events.append("before")

        async def after_run(self, run_id: str, env: str) -> None:
            events.append("after")

    runner = HookedRunner(session_factory, env=DEV, state_tracking=False)
    runner.register(ItemSeeder)
    await runner.fresh()
    assert events == ["before", "after"]


async def test_fresh_honours_transactional_mode(session_factory):
    class FailingSeeder(Seeder):
        environments = {DEV}
        models = [Item]

        async def run(self, session: AsyncSession) -> None:
            session.add(Item(name="never", value=1))
            await session.flush()
            raise RuntimeError("abort")

    runner = SeederRunner(
        session_factory, env=DEV, state_tracking=False, transactional=True
    )
    runner.register(FailingSeeder)
    with pytest.raises(RuntimeError):
        await runner.fresh()
    async with session_factory() as session:
        rows = (
            (await session.execute(select(Item).where(Item.name == "never")))
            .scalars()
            .all()
        )
    assert rows == []


async def test_failed_seeder_waits_for_siblings_in_same_level(session_factory):
    finished: list[str] = []

    class Fast(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            raise ValueError("fast failure")

    class Slow(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            await asyncio.sleep(0.05)
            finished.append("slow")

    runner = SeederRunner(session_factory, env=DEV, state_tracking=False)
    runner.register(Fast, Slow)
    with pytest.raises(ValueError, match="fast failure"):
        await runner.run()
    assert finished == ["slow"]


async def test_seeder_class_defaults_are_immutable():
    assert Seeder.depends_on == ()
    assert Seeder.models == ()
    assert Seeder.tags == frozenset()


def test_resolver_internals_not_in_public_api():
    import seedling

    assert "topological_sort" not in seedling.__all__
    assert not hasattr(seedling, "resolve_with_deps")


async def test_transactional_session_survives_commit(
    seedling_transactional_session, session_factory
):
    session = seedling_transactional_session
    session.add(Item(name="committed_in_test", value=1))
    await session.commit()
    found = (
        await session.execute(select(Item).where(Item.name == "committed_in_test"))
    ).scalar_one()
    assert found.value == 1


async def test_transactional_session_commit_is_rolled_back(session_factory):
    from seedling import pytest_plugin

    fixture_fn = pytest_plugin.seedling_transactional_session.__wrapped__
    agen = fixture_fn(session_factory)
    session = await agen.__anext__()
    session.add(Item(name="leaked", value=1))
    await session.commit()
    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()

    async with session_factory() as check:
        leaked = (
            (await check.execute(select(Item).where(Item.name == "leaked")))
            .scalars()
            .all()
        )
    assert leaked == []

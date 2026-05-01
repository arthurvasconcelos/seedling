"""Tests for seedling.helpers — upsert, truncate_tables, reset_sequences, deferred_constraints.

Dialect matrix
--------------
All tests run against SQLite (always available via aiosqlite).
PostgreSQL tests run when SEEDLING_TEST_PG_URL is set in the environment.
MariaDB tests run when SEEDLING_TEST_MARIADB_URL is set in the environment.
CI sets both; local runs skip them silently.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from seedling.helpers import (
    deferred_constraints,
    reset_sequences,
    truncate_tables,
    upsert,
)

# ── Test models ─────────────────────────────────────────────────────────────


class HBase(DeclarativeBase):
    pass


class Widget(HBase):
    __tablename__ = "widgets"
    __table_args__ = (UniqueConstraint("code", name="uq_widgets_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    label: Mapped[str] = mapped_column(String(100), default="")


class Gadget(HBase):
    __tablename__ = "gadgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))


# ── Parametrised engine fixture ──────────────────────────────────────────────

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"
_PG_URL = os.environ.get("SEEDLING_TEST_PG_URL", "")
_MARIADB_URL = os.environ.get("SEEDLING_TEST_MARIADB_URL", "")

_DIALECT_PARAMS = [
    pytest.param(_SQLITE_URL, id="sqlite"),
    pytest.param(
        _PG_URL,
        id="postgresql",
        marks=pytest.mark.skipif(not _PG_URL, reason="SEEDLING_TEST_PG_URL not set"),
    ),
    pytest.param(
        _MARIADB_URL,
        id="mariadb",
        marks=pytest.mark.skipif(
            not _MARIADB_URL, reason="SEEDLING_TEST_MARIADB_URL not set"
        ),
    ),
]


@pytest.fixture(params=_DIALECT_PARAMS)
async def db_session(request):
    url: str = request.param
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(HBase.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(HBase.metadata.drop_all)
    await engine.dispose()


# ── upsert ───────────────────────────────────────────────────────────────────


async def test_upsert_inserts_new_row(db_session: AsyncSession):
    await upsert(db_session, Widget, {"code": "W1", "label": "first"})
    await db_session.commit()

    result = await db_session.get(Widget, 1)
    assert result is not None
    assert result.code == "W1"


async def test_upsert_ignores_duplicate(db_session: AsyncSession):
    await upsert(db_session, Widget, {"code": "W2", "label": "original"})
    await db_session.commit()
    await upsert(db_session, Widget, {"code": "W2", "label": "updated"})
    await db_session.commit()

    from sqlalchemy import select

    rows = (await db_session.execute(select(Widget).where(Widget.code == "W2"))).scalars().all()
    assert len(rows) == 1
    assert rows[0].label == "original"


# ── truncate_tables ──────────────────────────────────────────────────────────


async def test_truncate_tables_removes_all_rows(db_session: AsyncSession):
    db_session.add(Widget(code="A", label="a"))
    db_session.add(Widget(code="B", label="b"))
    await db_session.commit()

    await truncate_tables(db_session, Widget)
    await db_session.commit()

    from sqlalchemy import select

    rows = (await db_session.execute(select(Widget))).scalars().all()
    assert rows == []


async def test_truncate_tables_multiple_models(db_session: AsyncSession):
    db_session.add(Widget(code="X", label="x"))
    db_session.add(Gadget(name="g1"))
    await db_session.commit()

    await truncate_tables(db_session, Widget, Gadget)
    await db_session.commit()

    from sqlalchemy import select

    widgets = (await db_session.execute(select(Widget))).scalars().all()
    gadgets = (await db_session.execute(select(Gadget))).scalars().all()
    assert widgets == []
    assert gadgets == []


# ── reset_sequences ───────────────────────────────────────────────────────────


async def test_reset_sequences_is_noop_on_sqlite(db_session: AsyncSession):
    conn = await db_session.connection()
    if conn.dialect.name != "sqlite":
        pytest.skip("SQLite-only test")

    db_session.add(Widget(code="seq1", label=""))
    await db_session.commit()
    await reset_sequences(db_session, Widget)
    await db_session.commit()


async def test_reset_sequences_resets_pk_counter_on_pg(db_session: AsyncSession):
    conn = await db_session.connection()
    if conn.dialect.name != "postgresql":
        pytest.skip("PostgreSQL-only test")

    db_session.add(Widget(code="s1", label=""))
    db_session.add(Widget(code="s2", label=""))
    await db_session.commit()

    await truncate_tables(db_session, Widget)
    await db_session.commit()
    await reset_sequences(db_session, Widget)
    await db_session.commit()

    db_session.add(Widget(code="after", label=""))
    await db_session.flush()

    from sqlalchemy import select

    row = (await db_session.execute(select(Widget).where(Widget.code == "after"))).scalar_one()
    assert row.id == 1


# ── deferred_constraints ──────────────────────────────────────────────────────


async def test_deferred_constraints_is_noop_on_sqlite(db_session: AsyncSession):
    conn = await db_session.connection()
    if conn.dialect.name != "sqlite":
        pytest.skip("SQLite-only test")

    async with deferred_constraints(db_session):
        db_session.add(Widget(code="dc1", label=""))
    await db_session.commit()

    from sqlalchemy import select

    row = (await db_session.execute(select(Widget).where(Widget.code == "dc1"))).scalar_one()
    assert row.code == "dc1"


async def test_deferred_constraints_context_enters_and_exits(db_session: AsyncSession):
    async with deferred_constraints(db_session):
        db_session.add(Widget(code="dc2", label=""))
    await db_session.commit()

    from sqlalchemy import select

    row = (await db_session.execute(select(Widget).where(Widget.code == "dc2"))).scalar_one()
    assert row.code == "dc2"

from __future__ import annotations

import pytest
from sqlalchemy import Computed, FetchedValue, Integer, String, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from seedling.factory import AutoFactory, Factory, Sequence


class _Base(DeclarativeBase):
    pass


class PlainModel(_Base):
    __tablename__ = "refresh_plain"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))


class WithServerDefault(_Base):
    __tablename__ = "refresh_server_default"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    score: Mapped[int] = mapped_column(Integer, server_default=text("42"))


class WithServerOnUpdate(_Base):
    __tablename__ = "refresh_server_onupdate"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    badge: Mapped[str | None] = mapped_column(
        String(100), server_onupdate=FetchedValue(), nullable=True
    )


class WithComputed(_Base):
    __tablename__ = "refresh_computed"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    a: Mapped[int] = mapped_column(Integer)
    b: Mapped[int] = mapped_column(Integer)
    c: Mapped[int] = mapped_column(Integer, Computed("a + b", persisted=True))


class WithPythonDefault(_Base):
    __tablename__ = "refresh_python_default"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    value: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(100))


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def session(session_factory):
    async with session_factory() as s:
        yield s


@pytest.fixture(autouse=True)
def isolated_registry():
    from seedling.factory import _registry

    snapshot = dict(_registry)
    yield
    _registry.clear()
    _registry.update(snapshot)


# ── _needs_refresh() detection ───────────────────────────────────────────────


def test_plain_model_does_not_need_refresh():
    class PlainFactory(Factory[PlainModel]):
        model = PlainModel
        name = Sequence(lambda n: f"plain-{n}")

    assert PlainFactory._needs_refresh() is False


def test_server_default_needs_refresh():
    class WithServerDefaultFactory(Factory[WithServerDefault]):
        model = WithServerDefault

    assert WithServerDefaultFactory._needs_refresh() is True


def test_server_onupdate_needs_refresh():
    class WithServerOnUpdateFactory(Factory[WithServerOnUpdate]):
        model = WithServerOnUpdate
        name = Sequence(lambda n: f"row-{n}")

    assert WithServerOnUpdateFactory._needs_refresh() is True


def test_computed_column_needs_refresh():
    class WithComputedFactory(Factory[WithComputed]):
        model = WithComputed
        a = Sequence(lambda n: n)
        b = Sequence(lambda n: n + 1)

    assert WithComputedFactory._needs_refresh() is True


def test_python_default_does_not_need_refresh():
    class PythonDefaultFactory(Factory[WithPythonDefault]):
        model = WithPythonDefault
        name = Sequence(lambda n: f"row-{n}")

    assert PythonDefaultFactory._needs_refresh() is False


def test_needs_refresh_result_is_cached():
    class CachingFactory(Factory[PlainModel]):
        model = PlainModel
        name = Sequence(lambda n: f"plain-{n}")

    CachingFactory._needs_refresh()
    assert "_refresh_cache" in CachingFactory.__dict__
    # Second call must return same value without recomputing
    assert CachingFactory._needs_refresh() is False


def test_each_subclass_caches_independently():
    class FactoryA(Factory[PlainModel]):
        model = PlainModel
        name = Sequence(lambda n: f"a-{n}")

    class FactoryB(Factory[WithServerDefault]):
        model = WithServerDefault

    assert FactoryA._needs_refresh() is False
    assert FactoryB._needs_refresh() is True
    assert FactoryA.__dict__["_refresh_cache"] is False
    assert FactoryB.__dict__["_refresh_cache"] is True


# ── create() behaviour ───────────────────────────────────────────────────────


async def test_create_no_server_default_pk_populated(session):
    class PlainFactory(Factory[PlainModel]):
        model = PlainModel
        name = Sequence(lambda n: f"plain-{n}")

    item = await PlainFactory.create(session)
    assert item.id is not None
    assert isinstance(item.id, int)


async def test_create_server_default_value_resolved(session):
    """create() on a server_default model must return the DB-generated value."""

    class WithServerDefaultFactory(Factory[WithServerDefault]):
        model = WithServerDefault

    inst = await WithServerDefaultFactory.create(session)
    assert inst.id is not None
    assert inst.score == 42


async def test_create_computed_value_resolved(session):
    """create() on a model with Computed column returns the DB-computed value."""

    class WithComputedFactory(Factory[WithComputed]):
        model = WithComputed
        a = Sequence(lambda n: n + 1)
        b = Sequence(lambda n: n + 2)

    inst = await WithComputedFactory.create(session)
    assert inst.c == inst.a + inst.b


async def test_autofactory_create_no_refresh_populates_pk(session):
    class ItemAutoFactory(AutoFactory[PlainModel]):
        model = PlainModel

    item = await ItemAutoFactory.create(session)
    assert item.id is not None
    assert item.name is not None

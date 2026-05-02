"""
Smoke tests for example apps.

The script example runs fully end-to-end against an in-memory SQLite database.
The FastAPI and Litestar examples are import-only tests — they verify that all
modules are importable and the factory/seeder wiring is correct, without
starting a server or requiring a PostgreSQL instance.
"""

from __future__ import annotations

import importlib
import pytest


# ── script example ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_script_example_end_to_end():
    """Run the script example's full seed+export cycle against SQLite."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from examples.script.models import Base
    from examples.script.seeders import create_runner

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    runner = create_runner(session_factory, env="development")

    await runner.run()

    data = await runner.export()
    assert "users" in data
    assert "posts" in data
    assert len(data["users"]) == 10
    assert len(data["posts"]) == 30

    await engine.dispose()


@pytest.mark.asyncio
async def test_script_example_fresh_cycle():
    """Verify fresh() truncates and re-seeds correctly."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from examples.script.models import Base
    from examples.script.seeders import create_runner

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    runner = create_runner(session_factory, env="development")

    await runner.run()
    await runner.fresh()

    data = await runner.export()
    assert len(data["users"]) == 10
    assert len(data["posts"]) == 30

    await engine.dispose()


# ── fastapi_alembic example — import-only ─────────────────────────────────────


@pytest.mark.skipif(
    importlib.util.find_spec("fastapi") is None,
    reason="fastapi not installed",
)
def test_fastapi_alembic_models_importable():
    mod = importlib.import_module("examples.fastapi_alembic.app.models")
    assert hasattr(mod, "User")
    assert hasattr(mod, "Post")


@pytest.mark.skipif(
    importlib.util.find_spec("fastapi") is None,
    reason="fastapi not installed",
)
def test_fastapi_alembic_factories_importable():
    mod = importlib.import_module("examples.fastapi_alembic.app.factories")
    assert hasattr(mod, "UserFactory")
    assert hasattr(mod, "PostFactory")


@pytest.mark.skipif(
    importlib.util.find_spec("fastapi") is None,
    reason="fastapi not installed",
)
def test_fastapi_alembic_seeders_importable():
    mod = importlib.import_module("examples.fastapi_alembic.app.seeders.users")
    assert hasattr(mod, "UserSeeder")
    mod2 = importlib.import_module("examples.fastapi_alembic.app.seeders.posts")
    assert hasattr(mod2, "PostSeeder")


# ── litestar example — import-only ────────────────────────────────────────────


@pytest.mark.skipif(
    importlib.util.find_spec("litestar") is None,
    reason="litestar not installed",
)
def test_litestar_models_importable():
    mod = importlib.import_module("examples.litestar.app.models")
    assert hasattr(mod, "User")
    assert hasattr(mod, "Post")


@pytest.mark.skipif(
    importlib.util.find_spec("litestar") is None,
    reason="litestar not installed",
)
def test_litestar_factories_importable():
    mod = importlib.import_module("examples.litestar.app.factories")
    assert hasattr(mod, "UserFactory")
    assert hasattr(mod, "PostFactory")


@pytest.mark.skipif(
    importlib.util.find_spec("litestar") is None,
    reason="litestar not installed",
)
def test_litestar_seeders_importable():
    mod = importlib.import_module("examples.litestar.app.seeders.users")
    assert hasattr(mod, "UserSeeder")
    mod2 = importlib.import_module("examples.litestar.app.seeders.posts")
    assert hasattr(mod2, "PostSeeder")

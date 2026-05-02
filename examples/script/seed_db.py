"""
Plain SQLAlchemy script — seed a local SQLite database.

Usage:
    uv run python -m examples.script.seed_db
    uv run python -m examples.script.seed_db --env development
    uv run python -m examples.script.seed_db --fresh
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from examples.script.models import Base
from examples.script.seeders import create_runner

DATABASE_URL = "sqlite+aiosqlite:///./script_example.db"


async def main(env: str, fresh: bool) -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    runner = create_runner(session_factory, env=env)

    if fresh:
        await runner.fresh()
    else:
        await runner.run()

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the script example database")
    parser.add_argument("--env", default="development")
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.env, args.fresh))

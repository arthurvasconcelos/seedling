from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from seedling import SeederRunner

from examples.fastapi_alembic.app.seeders.posts import PostSeeder
from examples.fastapi_alembic.app.seeders.users import UserSeeder


def create_runner(env: str) -> SeederRunner:
    from examples.fastapi_alembic.app.database import async_session
    runner = SeederRunner(async_session, env=env)
    runner.register(UserSeeder, PostSeeder)
    return runner

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from examples.script.seeders.posts import PostSeeder
from examples.script.seeders.users import UserSeeder
from seedling import SeederRunner


def create_runner(
    session_factory: async_sessionmaker[AsyncSession],
    env: str = "development",
) -> SeederRunner:
    runner = SeederRunner(session_factory, env=env)
    runner.register(UserSeeder, PostSeeder)
    return runner

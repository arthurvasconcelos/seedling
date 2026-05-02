from __future__ import annotations

from examples.litestar.app.seeders.posts import PostSeeder
from examples.litestar.app.seeders.users import UserSeeder
from seedling import SeederRunner


def create_runner(env: str) -> SeederRunner:
    from examples.litestar.app.database import async_session

    runner = SeederRunner(async_session, env=env)
    runner.register(UserSeeder, PostSeeder)
    return runner

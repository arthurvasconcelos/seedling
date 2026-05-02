from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from seedling import Seeder, DEV_AND_TEST, truncate_tables
from examples.fastapi_alembic.app.factories.post import PostFactory
from examples.fastapi_alembic.app.models import Post, User
from examples.fastapi_alembic.app.seeders.users import UserSeeder


class PostSeeder(Seeder):
    depends_on = [UserSeeder]
    environments = DEV_AND_TEST
    models = [Post]

    async def run(self, session: AsyncSession) -> None:
        users = (await session.execute(select(User))).scalars().all()
        for user in users:
            await PostFactory.create_batch(session, 3, author_id=user.id)
        await session.commit()

    async def truncate(self, session: AsyncSession) -> None:
        await truncate_tables(session, Post)
        await session.commit()

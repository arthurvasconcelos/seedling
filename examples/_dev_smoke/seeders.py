"""Seeders for the smoke test app."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from seedling import DEV_AND_TEST, Seeder, upsert

from .factories import PostFactory, UserFactory
from .models import Post, User


class UserSeeder(Seeder):
    environments = DEV_AND_TEST
    models = [User]

    async def run(self, session: AsyncSession) -> None:
        await upsert(session, User, {"email": "admin@example.com", "name": "Admin"})
        await UserFactory.create_batch(session, 4)
        await session.commit()

    async def truncate(self, session: AsyncSession) -> None:
        from sqlalchemy import delete

        await session.execute(delete(Post))
        await session.execute(delete(User))
        await session.commit()


class PostSeeder(Seeder):
    depends_on = [UserSeeder]
    environments = DEV_AND_TEST
    models = [Post]

    async def run(self, session: AsyncSession) -> None:
        await PostFactory.create_batch(session, 10)
        await session.commit()

    async def truncate(self, session: AsyncSession) -> None:
        from sqlalchemy import delete

        await session.execute(delete(Post))
        await session.commit()

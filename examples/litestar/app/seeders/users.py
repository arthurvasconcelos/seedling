from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from examples.litestar.app.factories.user import UserFactory
from examples.litestar.app.models import User
from seedling import DEV_AND_TEST, Seeder, truncate_tables


class UserSeeder(Seeder):
    environments = DEV_AND_TEST
    models = [User]
    tags = {"demo"}

    async def run(self, session: AsyncSession) -> None:
        await UserFactory.create_batch(session, 20)
        await session.commit()

    async def truncate(self, session: AsyncSession) -> None:
        await truncate_tables(session, User)
        await session.commit()

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from seedling.environments import DEV
from seedling.seeder import Seeder
from tests.conftest import Item


class DiscoverableUserSeeder(Seeder):
    environments = {DEV}

    async def run(self, session: AsyncSession) -> None:
        session.add(Item(name="discovered_user", value=10))
        await session.commit()

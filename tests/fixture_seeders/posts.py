from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from seedling.environments import DEV
from seedling.seeder import Seeder
from tests.conftest import Item
from tests.fixture_seeders.users import DiscoverableUserSeeder


class DiscoverablePostSeeder(Seeder):
    depends_on = [DiscoverableUserSeeder]
    environments = {DEV}

    async def run(self, session: AsyncSession) -> None:
        session.add(Item(name="discovered_post", value=20))
        await session.commit()

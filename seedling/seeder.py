from __future__ import annotations

from typing import Any, ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from seedling.environments import DEV_AND_TEST


class Seeder:
    # Seeder classes this one depends on. Runner ensures they run first.
    depends_on: ClassVar[list[type[Seeder]]] = []

    # When True, the library's upsert() helper uses on_conflict_do_nothing().
    # When False, the seeder manages its own idempotency (or relies on fresh).
    idempotent: ClassVar[bool] = True

    # Runner skips this seeder if the current env is not in this set.
    environments: ClassVar[set[str]] = DEV_AND_TEST

    # SQLAlchemy ORM model classes seeded by this seeder.
    # Declared here to support `seed export`.
    models: ClassVar[list[Any]] = []

    async def run(self, session: AsyncSession) -> None:
        raise NotImplementedError

    async def truncate(self, session: AsyncSession) -> None:
        # Default no-op. Override to customise truncation (e.g. CASCADE).
        pass

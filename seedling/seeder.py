from __future__ import annotations

from collections.abc import Sequence, Set
from typing import Any, ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from seedling.environments import DEV_AND_TEST


class Seeder:
    # Seeder classes this one depends on. Runner ensures they run first.
    depends_on: ClassVar[Sequence[type[Seeder]]] = ()

    # Informational flag surfaced by `seed list --verbose`. Declares whether the
    # seeder is safe to re-run without `fresh`; the runner does not act on it.
    idempotent: ClassVar[bool] = True

    # Runner skips this seeder if the current env is not in this set.
    environments: ClassVar[set[str]] = DEV_AND_TEST

    # SQLAlchemy ORM model classes seeded by this seeder.
    # Declared here to support `seed export`.
    models: ClassVar[Sequence[Any]] = ()

    # Optional labels for tag-based filtering (e.g. seed run --tag demo).
    tags: ClassVar[Set[str]] = frozenset()

    async def run(self, session: AsyncSession) -> None:
        raise NotImplementedError

    async def truncate(self, session: AsyncSession) -> None:
        pass

    async def before_run(self, session: AsyncSession) -> None:
        pass

    async def after_run(self, session: AsyncSession) -> None:
        pass

    async def on_error(self, session: AsyncSession, exc: BaseException) -> None:
        pass

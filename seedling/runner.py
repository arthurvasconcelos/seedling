from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from seedling.resolver import resolve_with_deps, topological_sort
from seedling.seeder import Seeder


class SeederRunner:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        env: str = "development",
    ) -> None:
        self._session_factory = session_factory
        self._env = env
        self._registry: list[type[Seeder]] = []

    def register(self, *seeder_classes: type[Seeder]) -> None:
        for cls in seeder_classes:
            if cls not in self._registry:
                self._registry.append(cls)

    def get_by_name(self, name: str) -> type[Seeder]:
        for cls in self._registry:
            if cls.__name__ == name:
                return cls
        raise ValueError(f"Unknown seeder: {name!r}")

    def list_seeders(self, *seeder_classes: type[Seeder]) -> list[type[Seeder]]:
        """Return ordered list filtered by env. Does not execute anything."""
        if seeder_classes:
            ordered = resolve_with_deps(list(seeder_classes), self._registry)
        else:
            ordered = topological_sort(self._registry)
        return [s for s in ordered if self._env in s.environments]

    async def run(self, *seeder_classes: type[Seeder]) -> None:
        """Run seeders in dependency order, filtered by env."""
        for seeder_cls in self.list_seeders(*seeder_classes):
            print(f"Running {seeder_cls.__name__}...")
            async with self._session_factory() as session:
                await seeder_cls().run(session)

    async def fresh(self, *seeder_classes: type[Seeder]) -> None:
        """Truncate affected tables in reverse order, then run."""
        to_run = self.list_seeders(*seeder_classes)
        for seeder_cls in reversed(to_run):
            async with self._session_factory() as session:
                await seeder_cls().truncate(session)
                await session.commit()
        for seeder_cls in to_run:
            print(f"Running {seeder_cls.__name__}...")
            async with self._session_factory() as session:
                await seeder_cls().run(session)

from __future__ import annotations

import asyncio
import importlib
import pkgutil
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from seedling.resolver import resolve_with_deps, topological_levels, topological_sort
from seedling.seeder import Seeder


def _all_subclasses(cls: type) -> set[type]:
    result: set[type] = set()
    for sub in cls.__subclasses__():
        result.add(sub)
        result.update(_all_subclasses(sub))
    return result


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

    def discover(self, package: str) -> None:
        """Import all modules under *package* and register any Seeder subclasses found."""
        pkg = importlib.import_module(package)
        prefix = pkg.__name__ + "."
        for _, name, _ in pkgutil.walk_packages(pkg.__path__, prefix):
            importlib.import_module(name)
        for cls in _all_subclasses(Seeder):
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

    def _list_levels(self, *seeder_classes: type[Seeder]) -> list[list[type[Seeder]]]:
        """Return env-filtered seeders grouped by parallel execution level."""
        if seeder_classes:
            subset = resolve_with_deps(list(seeder_classes), self._registry)
            levels = topological_levels(subset)
        else:
            levels = topological_levels(self._registry)
        return [
            [s for s in level if self._env in s.environments]
            for level in levels
            if any(self._env in s.environments for s in level)
        ]

    async def _run_one(self, seeder_cls: type[Seeder]) -> None:
        print(f"Running {seeder_cls.__name__}...")
        async with self._session_factory() as session:
            await seeder_cls().run(session)

    async def _truncate_one(self, seeder_cls: type[Seeder]) -> None:
        async with self._session_factory() as session:
            await seeder_cls().truncate(session)
            await session.commit()

    async def run(self, *seeder_classes: type[Seeder]) -> None:
        """Run seeders level by level; seeders within a level run in parallel."""
        for level in self._list_levels(*seeder_classes):
            await asyncio.gather(*[self._run_one(cls) for cls in level])

    async def fresh(self, *seeder_classes: type[Seeder]) -> None:
        """Truncate affected tables in reverse level order, then run."""
        levels = self._list_levels(*seeder_classes)
        for level in reversed(levels):
            await asyncio.gather(*[self._truncate_one(cls) for cls in level])
        for level in levels:
            await asyncio.gather(*[self._run_one(cls) for cls in level])

    async def export(
        self, *seeder_classes: type[Seeder]
    ) -> dict[str, list[dict[str, Any]]]:
        """Query all rows for models declared on registered seeders.

        Returns a dict keyed by table name. Only seeders that declare
        ``models = [...]`` contribute to the export.
        """
        candidates = list(seeder_classes) if seeder_classes else self._registry
        seen: set[Any] = set()
        ordered_models: list[Any] = []
        for seeder_cls in candidates:
            for model in seeder_cls.models:
                if model not in seen:
                    ordered_models.append(model)
                    seen.add(model)

        result: dict[str, list[dict[str, Any]]] = {}
        async with self._session_factory() as session:
            for model in ordered_models:
                mapper = sa_inspect(model)
                col_keys = [c.key for c in mapper.mapper.column_attrs]
                rows = (await session.execute(select(model))).scalars().all()
                result[model.__tablename__] = [
                    {key: getattr(row, key) for key in col_keys} for row in rows
                ]
        return result

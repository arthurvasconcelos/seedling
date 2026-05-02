from __future__ import annotations

import asyncio
import importlib
import pkgutil
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from seedling.resolver import resolve_with_deps, topological_levels, topological_sort
from seedling.seeder import Seeder
from seedling.state import (
    compute_hash,
    delete_states_for_seeders,
    ensure_state_table,
    get_latest_states,
    insert_state_row,
    update_state_row,
)

_log = structlog.get_logger(__name__)


class _NoCommitSession:
    """Wraps AsyncSession and makes commit() a no-op.

    Used in transactional mode so individual seeders don't prematurely close
    the shared outer transaction. The runner commits (or rolls back) at the end.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        pass

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)


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
        *,
        state_tracking: bool = True,
        transactional: bool = False,
        max_parallel: int | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._env = env
        self._state_tracking = state_tracking
        self._transactional = transactional
        self._max_parallel = max_parallel
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

    # ── Runner-level lifecycle hooks ─────────────────────────────────────────

    async def before_run(self, run_id: str, env: str) -> None:
        pass

    async def after_run(self, run_id: str, env: str) -> None:
        pass

    async def on_run_error(self, run_id: str, env: str, exc: BaseException) -> None:
        pass

    # ── Internals ────────────────────────────────────────────────────────────

    async def _run_one(
        self,
        seeder_cls: type[Seeder],
        log: structlog.types.FilteringBoundLogger,
        run_id: str,
        on_start: Callable[[str], None] | None,
        on_finish: Callable[[str], None] | None,
        shared_session: AsyncSession | None = None,
    ) -> None:
        """Execute one seeder with hooks and optional state tracking.

        Each call opens its own state session so parallel seeders don't
        share a connection.
        """
        log.info("seeder.start", seeder=seeder_cls.__name__)
        if on_start:
            on_start(seeder_cls.__name__)

        row_id: int | None = None
        content_hash = (
            compute_hash(seeder_cls)
            if self._state_tracking and shared_session is None
            else None
        )

        started_at = datetime.now(UTC)
        try:
            if shared_session is not None:
                # Transactional mode: state tracking skipped (shared txn could roll back).
                instance = seeder_cls()
                await instance.before_run(shared_session)
                await instance.run(shared_session)
                await instance.after_run(shared_session)
            else:
                if self._state_tracking:
                    async with self._session_factory() as state_session:
                        row_id = await insert_state_row(
                            state_session,
                            seeder_name=seeder_cls.__name__,
                            env=self._env,
                            run_id=run_id,
                            content_hash=content_hash,
                        )

                async with self._session_factory() as session:
                    instance = seeder_cls()
                    await instance.before_run(session)
                    await instance.run(session)
                    await instance.after_run(session)

        except Exception as exc:
            finished_at = datetime.now(UTC)
            duration_ms = int((finished_at - started_at).total_seconds() * 1000)
            if self._state_tracking and row_id is not None:
                async with self._session_factory() as state_session:
                    await update_state_row(
                        state_session,
                        row_id,
                        status="error",
                        finished_at=finished_at,
                        duration_ms=duration_ms,
                        error=str(exc),
                    )
            log.error("seeder.error", seeder=seeder_cls.__name__, error=str(exc))
            raise

        finished_at = datetime.now(UTC)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        if self._state_tracking and row_id is not None:
            async with self._session_factory() as state_session:
                await update_state_row(
                    state_session,
                    row_id,
                    status="success",
                    finished_at=finished_at,
                    duration_ms=duration_ms,
                )
        log.info("seeder.finish", seeder=seeder_cls.__name__)
        if on_finish:
            on_finish(seeder_cls.__name__)

    async def _truncate_one(self, seeder_cls: type[Seeder]) -> None:
        async with self._session_factory() as session:
            await seeder_cls().truncate(session)
            await session.commit()

    async def _ensure_state_table_once(self) -> None:
        async with self._session_factory() as session:
            await ensure_state_table(session)

    async def _compute_skip_set(self, levels: list[list[type[Seeder]]]) -> set[str]:
        all_names = [cls.__name__ for level in levels for cls in level]
        async with self._session_factory() as session:
            latest = await get_latest_states(session, all_names, self._env)
        skip: set[str] = set()
        for cls in (c for level in levels for c in level):
            entry = latest.get(cls.__name__)
            if (
                entry
                and entry["status"] == "success"
                and entry["content_hash"] is not None
                and entry["content_hash"] == compute_hash(cls)
            ):
                skip.add(cls.__name__)
        return skip

    async def run(
        self,
        *seeder_classes: type[Seeder],
        on_seeder_start: Callable[[str], None] | None = None,
        on_seeder_finish: Callable[[str], None] | None = None,
        new_only: bool = False,
        force: bool = False,
    ) -> None:
        """Run seeders level by level; seeders within a level run in parallel."""
        run_id = str(uuid.uuid4())
        log = _log.bind(run_id=run_id, env=self._env)
        levels = self._list_levels(*seeder_classes)
        log.info("run.start", seeder_count=sum(len(level) for level in levels))

        await self.before_run(run_id, self._env)
        try:
            if self._transactional:
                await self._run_transactional(
                    levels, log, run_id, on_seeder_start, on_seeder_finish
                )
            else:
                await self._run_normal(
                    levels,
                    log,
                    run_id,
                    on_seeder_start,
                    on_seeder_finish,
                    new_only=new_only and not force,
                )
        except Exception as exc:
            await self.on_run_error(run_id, self._env, exc)
            raise

        await self.after_run(run_id, self._env)
        log.info("run.finish")

    async def _run_normal(
        self,
        levels: list[list[type[Seeder]]],
        log: structlog.types.FilteringBoundLogger,
        run_id: str,
        on_start: Callable[[str], None] | None,
        on_finish: Callable[[str], None] | None,
        *,
        new_only: bool = False,
    ) -> None:
        semaphore = (
            asyncio.Semaphore(self._max_parallel) if self._max_parallel else None
        )

        if self._state_tracking:
            await self._ensure_state_table_once()

        skip_set: set[str] = set()
        if new_only and self._state_tracking:
            skip_set = await self._compute_skip_set(levels)

        async def _bounded(cls: type[Seeder]) -> None:
            if semaphore:
                async with semaphore:
                    await self._run_one(cls, log, run_id, on_start, on_finish)
            else:
                await self._run_one(cls, log, run_id, on_start, on_finish)

        for level in levels:
            active = [cls for cls in level if cls.__name__ not in skip_set]
            if active:
                await asyncio.gather(*[_bounded(cls) for cls in active])

    async def _run_transactional(
        self,
        levels: list[list[type[Seeder]]],
        log: structlog.types.FilteringBoundLogger,
        run_id: str,
        on_start: Callable[[str], None] | None,
        on_finish: Callable[[str], None] | None,
    ) -> None:
        # All seeders share one session/transaction; sequential within each level.
        # State tracking is skipped — the shared transaction would roll back state
        # rows along with seeder data, making audit records unreliable.
        # All seeders share one wrapped session. The wrapper makes commit() a
        # no-op so individual seeders don't close the outer transaction — the
        # runner commits at the end (or rolls back if any seeder raises).
        async with self._session_factory() as shared_session:
            async with shared_session.begin():
                wrapped = _NoCommitSession(shared_session)
                for level in levels:
                    for cls in level:
                        await self._run_one(
                            cls,
                            log,
                            run_id,
                            on_start,
                            on_finish,
                            cast(AsyncSession, wrapped),
                        )

    async def fresh(
        self,
        *seeder_classes: type[Seeder],
        on_seeder_start: Callable[[str], None] | None = None,
        on_seeder_finish: Callable[[str], None] | None = None,
    ) -> None:
        """Truncate affected tables in reverse level order, then run."""
        run_id = str(uuid.uuid4())
        log = _log.bind(run_id=run_id, env=self._env)
        levels = self._list_levels(*seeder_classes)
        log.info("fresh.start", seeder_count=sum(len(level) for level in levels))

        if self._state_tracking:
            all_names = [cls.__name__ for level in levels for cls in level]
            async with self._session_factory() as state_session:
                await ensure_state_table(state_session)
                await delete_states_for_seeders(state_session, all_names, self._env)

        for level in reversed(levels):
            await asyncio.gather(*[self._truncate_one(cls) for cls in level])

        await self._run_normal(levels, log, run_id, on_seeder_start, on_seeder_finish)
        log.info("fresh.finish")

    async def export(
        self, *seeder_classes: type[Seeder]
    ) -> dict[str, list[dict[str, Any]]]:
        """Query all rows for models declared on registered seeders."""
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

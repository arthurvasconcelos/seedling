from __future__ import annotations

import hashlib
import inspect
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession

from seedling.seeder import Seeder

_metadata = MetaData()

state_table = Table(
    "seedling_state",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("seeder_name", String(255), nullable=False),
    Column("env", String(100), nullable=False),
    Column("run_id", String(36), nullable=False),
    Column("status", String(20), nullable=False),
    Column("started_at", DateTime, nullable=False),
    Column("finished_at", DateTime, nullable=True),
    Column("duration_ms", Integer, nullable=True),
    Column("error", Text, nullable=True),
    Column("rows_seeded", Integer, nullable=True),
    Column("content_hash", String(64), nullable=True),
    Index("ix_seedling_state_seeder_env", "seeder_name", "env"),
)


async def ensure_state_table(session: AsyncSession) -> None:
    """Create seedling_state if it does not already exist."""
    conn = await session.connection()
    await conn.run_sync(state_table.create, checkfirst=True)
    await session.commit()


def compute_hash(seeder_cls: type[Seeder]) -> str | None:
    """SHA-256 of seeder_cls.run source. Returns None if source is unavailable."""
    try:
        source = inspect.getsource(seeder_cls.run)
    except (OSError, TypeError):
        return None
    return hashlib.sha256(source.encode()).hexdigest()


async def insert_state_row(
    session: AsyncSession,
    *,
    seeder_name: str,
    env: str,
    run_id: str,
    content_hash: str | None,
) -> int:
    """Insert a row with status='running'. Returns the new row id."""
    result = await session.execute(
        state_table.insert().values(
            seeder_name=seeder_name,
            env=env,
            run_id=run_id,
            status="running",
            started_at=datetime.now(UTC).replace(tzinfo=None),
            content_hash=content_hash,
        )
    )
    await session.commit()
    return int(cast(Any, result).inserted_primary_key[0])


async def update_state_row(
    session: AsyncSession,
    row_id: int,
    *,
    status: str,
    finished_at: datetime,
    duration_ms: int,
    error: str | None = None,
    rows_seeded: int | None = None,
) -> None:
    """Update a row with final execution data."""
    await session.execute(
        state_table.update()
        .where(state_table.c.id == row_id)
        .values(
            status=status,
            finished_at=finished_at.replace(tzinfo=None),
            duration_ms=duration_ms,
            error=error,
            rows_seeded=rows_seeded,
        )
    )
    await session.commit()


async def get_latest_states(
    session: AsyncSession,
    seeder_names: list[str],
    env: str,
) -> dict[str, dict[str, Any]]:
    """Return the most-recent completed row per seeder name for the given env.

    Only 'success' and 'error' rows are included — in-progress rows are skipped
    so --new-only decisions are stable.
    """
    if not seeder_names:
        return {}

    conn = await session.connection()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        sql = text(
            """
            SELECT DISTINCT ON (seeder_name)
                id, seeder_name, env, run_id, status,
                started_at, finished_at, duration_ms, error, rows_seeded, content_hash
            FROM seedling_state
            WHERE seeder_name = ANY(:names)
              AND env = :env
              AND status IN ('success', 'error')
            ORDER BY seeder_name, id DESC
            """
        )
        rows = (await session.execute(sql, {"names": seeder_names, "env": env})).all()
    else:
        placeholders = ", ".join(f":n{i}" for i in range(len(seeder_names)))
        sql = text(
            f"""
            SELECT id, seeder_name, env, run_id, status,
                   started_at, finished_at, duration_ms, error, rows_seeded, content_hash
            FROM seedling_state
            WHERE seeder_name IN ({placeholders})
              AND env = :env
              AND status IN ('success', 'error')
            ORDER BY id DESC
            """
        )
        params: dict[str, Any] = {f"n{i}": n for i, n in enumerate(seeder_names)}
        params["env"] = env
        all_rows = (await session.execute(sql, params)).all()
        seen: set[str] = set()
        rows = []
        for row in all_rows:
            name = row[1]
            if name not in seen:
                seen.add(name)
                rows.append(row)

    cols = [
        "id",
        "seeder_name",
        "env",
        "run_id",
        "status",
        "started_at",
        "finished_at",
        "duration_ms",
        "error",
        "rows_seeded",
        "content_hash",
    ]
    return {row[1]: dict(zip(cols, row, strict=True)) for row in rows}


async def delete_states_for_seeders(
    session: AsyncSession,
    seeder_names: list[str],
    env: str,
) -> None:
    """Delete all state rows for the given seeders and env (used by fresh)."""
    if not seeder_names:
        return
    await session.execute(
        state_table.delete().where(
            state_table.c.seeder_name.in_(seeder_names),
            state_table.c.env == env,
        )
    )
    await session.commit()

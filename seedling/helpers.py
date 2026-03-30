from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


async def upsert(
    session: AsyncSession,
    model_class: type,
    values: dict[str, Any],
    constraint: str | None = None,
) -> None:
    """
    Dialect-aware idempotent insert.

    Uses ON CONFLICT DO NOTHING on PostgreSQL and INSERT OR IGNORE on SQLite.
    Requires a named UniqueConstraint when `constraint` is provided (PostgreSQL only).
    """
    conn = await session.connection()
    dialect = conn.dialect.name

    stmt: Any
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        pg_stmt = pg_insert(model_class).values(**values)
        stmt = (
            pg_stmt.on_conflict_do_nothing(constraint=constraint)
            if constraint
            else pg_stmt.on_conflict_do_nothing()
        )
    else:
        from sqlalchemy import insert

        stmt = insert(model_class).prefix_with("OR IGNORE").values(**values)

    await session.execute(stmt)

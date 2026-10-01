from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def upsert(
    session: AsyncSession,
    model_class: type[Any],
    values: dict[str, Any],
    constraint: str | None = None,
) -> None:
    """
    Dialect-aware idempotent insert.

    - PostgreSQL: ON CONFLICT DO NOTHING (or ON CONFLICT ON CONSTRAINT … DO NOTHING)
    - SQLite: INSERT OR IGNORE
    - MySQL / MariaDB: INSERT IGNORE
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
    elif dialect in ("mysql", "mariadb"):
        from sqlalchemy.dialects.mysql import insert as mysql_insert

        stmt = mysql_insert(model_class).prefix_with("IGNORE").values(**values)
    elif dialect == "sqlite":
        from sqlalchemy import insert

        stmt = insert(model_class).prefix_with("OR IGNORE").values(**values)
    else:
        raise NotImplementedError(f"upsert() does not support dialect {dialect!r}")

    await session.execute(stmt)


async def truncate_tables(
    session: AsyncSession, *models: type[Any], cascade: bool = True
) -> None:
    """
    Truncate tables for the given ORM models, dialect-aware.

    - PostgreSQL: TRUNCATE … [CASCADE]
    - MySQL / MariaDB: disables FK checks, truncates, re-enables FK checks
    - SQLite: DELETE FROM (no TRUNCATE support)
    """
    conn = await session.connection()
    dialect = conn.dialect.name
    names = [_qualified_table_name(conn.dialect, m) for m in models]

    if dialect == "postgresql":
        suffix = " CASCADE" if cascade else ""
        await session.execute(text(f"TRUNCATE {', '.join(names)}{suffix}"))
    elif dialect in ("mysql", "mariadb"):
        await session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for name in names:
            await session.execute(text(f"TRUNCATE TABLE {name}"))
        await session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    else:
        for name in names:
            await session.execute(text(f"DELETE FROM {name}"))


def _qualified_table_name(dialect: Any, model: type[Any]) -> str:
    table = sa_inspect(model).local_table
    return str(dialect.identifier_preparer.format_table(table))


async def reset_sequences(session: AsyncSession, *models: type[Any]) -> None:
    """
    Reset PostgreSQL SERIAL / IDENTITY sequences for the given ORM models to 1.

    No-op on SQLite and MySQL/MariaDB (those dialects do not use named sequences).
    """
    conn = await session.connection()
    if conn.dialect.name != "postgresql":
        return

    for model in models:
        mapper = sa_inspect(model)
        table_name = _qualified_table_name(conn.dialect, model)
        for col_obj in mapper.local_table.columns:
            if col_obj.autoincrement is True or (
                col_obj.primary_key and col_obj.autoincrement != False  # noqa: E712
            ):
                await session.execute(
                    text(
                        "SELECT setval(pg_get_serial_sequence(:table, :column), 1, false)"
                    ),
                    {"table": table_name, "column": col_obj.name},
                )


@asynccontextmanager
async def deferred_constraints(session: AsyncSession) -> AsyncIterator[None]:
    """
    Defer all constraints for the duration of the block (PostgreSQL only).

    On other dialects this is a no-op context manager.

    Usage::

        async with deferred_constraints(session):
            # FK violations are allowed here; constraints checked on COMMIT
            ...
    """
    conn = await session.connection()
    if conn.dialect.name == "postgresql":
        await session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
        try:
            yield
        finally:
            await session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    else:
        yield

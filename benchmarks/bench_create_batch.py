"""
Benchmark: per-row create() vs create_batch(bulk=True).

Usage:
    uv run python benchmarks/bench_create_batch.py

Results are printed to stdout. Run with --rows to change the batch size.
"""

from __future__ import annotations

import argparse
import asyncio
import time

from sqlalchemy import String
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from seedling import AutoFactory


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "bench_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    value: Mapped[int] = mapped_column(default=0)


class ItemFactory(AutoFactory[Item]):
    model = Item


async def run(rows: int) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Per-row path
    async with session_factory() as session:
        start = time.perf_counter()
        await ItemFactory.create_batch(session, rows)
        per_row_s = time.perf_counter() - start

    # Bulk path
    async with session_factory() as session:
        start = time.perf_counter()
        await ItemFactory.create_batch(session, rows, bulk=True)
        bulk_s = time.perf_counter() - start

    await engine.dispose()

    print(f"Rows: {rows:,}")
    print(f"  per-row : {per_row_s:.3f}s  ({rows / per_row_s:,.0f} rows/s)")
    print(f"  bulk    : {bulk_s:.3f}s  ({rows / bulk_s:,.0f} rows/s)")
    print(f"  speedup : {per_row_s / bulk_s:.1f}x")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=1_000)
    args = parser.parse_args()
    asyncio.run(run(args.rows))

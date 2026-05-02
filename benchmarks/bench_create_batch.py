"""
Benchmark: per-row create() vs create_batch(bulk=True).

Usage:
    uv run python benchmarks/bench_create_batch.py
    uv run python benchmarks/bench_create_batch.py --rows 5000
    uv run python benchmarks/bench_create_batch.py --json   # for CI tracking
"""

from __future__ import annotations

import argparse
import asyncio
import json
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


async def run(rows: int) -> tuple[float, float]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        start = time.perf_counter()
        await ItemFactory.create_batch(session, rows)
        per_row_s = time.perf_counter() - start

    async with session_factory() as session:
        start = time.perf_counter()
        await ItemFactory.create_batch(session, rows, bulk=True)
        bulk_s = time.perf_counter() - start

    await engine.dispose()
    return per_row_s, bulk_s


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=1_000)
    parser.add_argument(
        "--json", action="store_true", help="Output JSON for CI benchmark tracking"
    )
    args = parser.parse_args()

    per_row_s, bulk_s = asyncio.run(run(args.rows))

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "name": f"create_batch per-row {args.rows} rows",
                        "unit": "seconds",
                        "value": round(per_row_s, 4),
                    },
                    {
                        "name": f"create_batch bulk {args.rows} rows",
                        "unit": "seconds",
                        "value": round(bulk_s, 4),
                    },
                ]
            )
        )
    else:
        print(f"Rows: {args.rows:,}")
        print(f"  per-row : {per_row_s:.3f}s  ({args.rows / per_row_s:,.0f} rows/s)")
        print(f"  bulk    : {bulk_s:.3f}s  ({args.rows / bulk_s:,.0f} rows/s)")
        print(f"  speedup : {per_row_s / bulk_s:.1f}x")

"""
Benchmark: Seedling vs raw SQLAlchemy vs factory_boy.

Same scenario in every scenario — insert N rows into a single table with two
columns (a string and an int) — measured from a clean in-memory SQLite DB.

Fairness notes (read before sharing numbers):

- factory_boy is sync; it's measured against a sync SQLAlchemy engine because
  that is how it is actually used in the wild. The other scenarios use the
  async engine. The wall-clock number is what an async-app author experiences
  if they pick that tool, which is the point of the comparison.
- SQLite is in-memory, so per-row scenarios look better than they would on
  PostgreSQL where each round-trip pays real network latency. The bulk-insert
  gap widens further on a networked DB.
- Each scenario uses a fresh engine + schema to avoid cache contamination.

Usage:
    uv run python benchmarks/bench_vs_alternatives.py
    uv run python benchmarks/bench_vs_alternatives.py --rows 5000
    uv run python benchmarks/bench_vs_alternatives.py --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any, cast

import factory
from sqlalchemy import String, create_engine, insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from seedling import AutoFactory


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "bench_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    value: Mapped[int] = mapped_column(default=0)


class SeedlingItemFactory(AutoFactory[Item]):
    model = Item


class FactoryBoyItemFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Item
        sqlalchemy_session_persistence = "flush"

    name = factory.Sequence(lambda n: f"name-{n}")
    value = factory.Sequence(lambda n: n)


def _fresh_sync_session() -> Session:
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)()


async def _fresh_async_session_factory() -> async_sessionmaker:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


async def bench_raw_sqlalchemy_bulk(rows: int) -> float:
    session_factory = await _fresh_async_session_factory()
    async with session_factory() as session:
        payload = [{"name": f"name-{i}", "value": i} for i in range(rows)]
        start = time.perf_counter()
        await session.execute(insert(Item), payload)
        await session.flush()
        return time.perf_counter() - start


async def bench_raw_sqlalchemy_per_row(rows: int) -> float:
    session_factory = await _fresh_async_session_factory()
    async with session_factory() as session:
        start = time.perf_counter()
        for i in range(rows):
            session.add(Item(name=f"name-{i}", value=i))
        await session.flush()
        return time.perf_counter() - start


def bench_factory_boy(rows: int) -> float:
    session = _fresh_sync_session()
    cast(Any, FactoryBoyItemFactory._meta).sqlalchemy_session = session
    start = time.perf_counter()
    FactoryBoyItemFactory.create_batch(rows)
    session.flush()
    return time.perf_counter() - start


async def bench_seedling_per_row(rows: int) -> float:
    session_factory = await _fresh_async_session_factory()
    async with session_factory() as session:
        start = time.perf_counter()
        await SeedlingItemFactory.create_batch(session, rows)
        return time.perf_counter() - start


async def bench_seedling_bulk(rows: int) -> float:
    session_factory = await _fresh_async_session_factory()
    async with session_factory() as session:
        start = time.perf_counter()
        await SeedlingItemFactory.create_batch(session, rows, bulk=True)
        return time.perf_counter() - start


SCENARIOS: list[tuple[str, Callable[[int], Awaitable[float] | float]]] = [
    ("raw SQLAlchemy (bulk insert)", bench_raw_sqlalchemy_bulk),
    ("raw SQLAlchemy (per-row add)", bench_raw_sqlalchemy_per_row),
    ("factory_boy (sync)", bench_factory_boy),
    ("Seedling per-row", bench_seedling_per_row),
    ("Seedling bulk", bench_seedling_bulk),
]


async def run(rows: int) -> list[tuple[str, float]]:
    results: list[tuple[str, float]] = []
    for name, fn in SCENARIOS:
        result = fn(rows)
        elapsed = await result if asyncio.iscoroutine(result) else cast(float, result)
        results.append((name, elapsed))
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=1_000)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = asyncio.run(run(args.rows))

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "name": f"{name} ({args.rows} rows)",
                        "unit": "seconds",
                        "value": round(elapsed, 4),
                    }
                    for name, elapsed in results
                ]
            )
        )
    else:
        baseline = next(t for n, t in results if n == "raw SQLAlchemy (bulk insert)")
        print(f"Rows: {args.rows:,}  (in-memory SQLite, single machine)\n")
        name_w = max(len(n) for n, _ in results)
        print(f"  {'scenario'.ljust(name_w)}    time     rows/s    vs raw bulk")
        print(f"  {'-' * name_w}    -----    ------    -----------")
        for name, elapsed in results:
            rate = args.rows / elapsed
            ratio = elapsed / baseline
            print(
                f"  {name.ljust(name_w)}  {elapsed:6.3f}s  {rate:8,.0f}    {ratio:5.2f}x"
            )

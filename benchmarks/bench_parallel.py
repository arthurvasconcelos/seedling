"""
Benchmark: parallel level execution vs sequential.

Simulates a two-level seeder graph where each seeder does 200 per-row inserts.
Measures total wall-clock time with and without parallel execution.

Usage:
    uv run python benchmarks/bench_parallel.py
    uv run python benchmarks/bench_parallel.py --json   # for CI benchmark tracking
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time

from sqlalchemy import String
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from seedling import DEV_AND_TEST, AutoFactory, Seeder, SeederRunner


class Base(DeclarativeBase):
    pass


class Alpha(Base):
    __tablename__ = "bench_alpha"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))


class Beta(Base):
    __tablename__ = "bench_beta"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))


class Gamma(Base):
    __tablename__ = "bench_gamma"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))


class AlphaFactory(AutoFactory[Alpha]):
    model = Alpha


class BetaFactory(AutoFactory[Beta]):
    model = Beta


class GammaFactory(AutoFactory[Gamma]):
    model = Gamma


ROWS = 200


class AlphaSeeder(Seeder):
    environments = DEV_AND_TEST

    async def run(self, session):
        await AlphaFactory.create_batch(session, ROWS)


class BetaSeeder(Seeder):
    environments = DEV_AND_TEST

    async def run(self, session):
        await BetaFactory.create_batch(session, ROWS)


class GammaSeeder(Seeder):
    depends_on = [AlphaSeeder, BetaSeeder]
    environments = DEV_AND_TEST

    async def run(self, session):
        await GammaFactory.create_batch(session, ROWS)


async def run() -> tuple[float, float]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    runner = SeederRunner(session_factory, env="development", state_tracking=False)
    runner.register(AlphaSeeder, BetaSeeder, GammaSeeder)
    start = time.perf_counter()
    await runner.run()
    parallel_s = time.perf_counter() - start

    runner2 = SeederRunner(
        session_factory, env="development", state_tracking=False, max_parallel=1
    )
    runner2.register(AlphaSeeder, BetaSeeder, GammaSeeder)
    start = time.perf_counter()
    await runner2.run()
    sequential_s = time.perf_counter() - start

    await engine.dispose()
    return parallel_s, sequential_s


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json", action="store_true", help="Output JSON for CI benchmark tracking"
    )
    args = parser.parse_args()

    parallel_s, sequential_s = asyncio.run(run())

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "name": "parallel 3 seeders",
                        "unit": "seconds",
                        "value": round(parallel_s, 4),
                    },
                    {
                        "name": "sequential 3 seeders",
                        "unit": "seconds",
                        "value": round(sequential_s, 4),
                    },
                ]
            )
        )
    else:
        print(f"Seeders: 3 (Alpha + Beta in parallel, then Gamma)  |  {ROWS} rows each")
        print(f"  parallel   : {parallel_s:.3f}s")
        print(f"  sequential : {sequential_s:.3f}s")
        print(f"  speedup    : {sequential_s / parallel_s:.1f}x")

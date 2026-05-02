"""
Benchmark: parallel level execution vs sequential.

Simulates a two-level seeder graph where each seeder does 100 per-row inserts.
Measures total wall-clock time with and without parallel execution.

Usage:
    uv run python benchmarks/bench_parallel.py
"""

from __future__ import annotations

import asyncio
import time

from sqlalchemy import String
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from seedling import AutoFactory, SeederRunner, Seeder, DEV_AND_TEST


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


async def run() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Parallel (default): Alpha + Beta run simultaneously, then Gamma
    runner = SeederRunner(session_factory, env="development", state_tracking=False)
    runner.register(AlphaSeeder, BetaSeeder, GammaSeeder)
    start = time.perf_counter()
    await runner.run()
    parallel_s = time.perf_counter() - start

    # Sequential: cap parallelism to 1
    runner2 = SeederRunner(
        session_factory, env="development", state_tracking=False, max_parallel=1
    )
    runner2.register(AlphaSeeder, BetaSeeder, GammaSeeder)
    start = time.perf_counter()
    await runner2.run()
    sequential_s = time.perf_counter() - start

    await engine.dispose()

    print(f"Seeders: 3 (Alpha + Beta in parallel, then Gamma)  |  {ROWS} rows each")
    print(f"  parallel   : {parallel_s:.3f}s")
    print(f"  sequential : {sequential_s:.3f}s")
    print(f"  speedup    : {sequential_s / parallel_s:.1f}x")


if __name__ == "__main__":
    asyncio.run(run())

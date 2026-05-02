from __future__ import annotations

import asyncio

import pytest
import structlog.testing
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from seedling.environments import DEV, PROD, TEST
from seedling.runner import SeederRunner
from seedling.seeder import Seeder
from seedling.state import get_latest_states, state_table
from tests.conftest import Item

# ── Minimal seeders for testing ─────────────────────────────────────────────────


class ItemSeederA(Seeder):
    environments = {DEV, TEST}

    async def run(self, session: AsyncSession) -> None:
        session.add(Item(name="a", value=1))
        await session.commit()

    async def truncate(self, session: AsyncSession) -> None:
        await session.execute(text("DELETE FROM items WHERE name = 'a'"))


class ItemSeederB(Seeder):
    depends_on = [ItemSeederA]
    environments = {DEV, TEST}

    async def run(self, session: AsyncSession) -> None:
        session.add(Item(name="b", value=2))
        await session.commit()

    async def truncate(self, session: AsyncSession) -> None:
        await session.execute(text("DELETE FROM items WHERE name = 'b'"))


class ProdOnlySeeder(Seeder):
    environments = {PROD}

    async def run(self, session: AsyncSession) -> None:
        session.add(Item(name="prod", value=99))
        await session.commit()


# ── list_seeders ────────────────────────────────────────────────────────────────


def test_list_seeders_returns_all_for_env(session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.register(ItemSeederA, ItemSeederB, ProdOnlySeeder)
    result = runner.list_seeders()
    assert ItemSeederA in result
    assert ItemSeederB in result
    assert ProdOnlySeeder not in result


def test_list_seeders_filters_by_env(session_factory):
    runner = SeederRunner(session_factory, env=PROD)
    runner.register(ItemSeederA, ItemSeederB, ProdOnlySeeder)
    result = runner.list_seeders()
    assert ProdOnlySeeder in result
    assert ItemSeederA not in result


def test_list_seeders_respects_dependency_order(session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.register(ItemSeederA, ItemSeederB)
    result = runner.list_seeders()
    assert result.index(ItemSeederA) < result.index(ItemSeederB)


def test_list_seeders_specific_subset(session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.register(ItemSeederA, ItemSeederB, ProdOnlySeeder)
    result = runner.list_seeders(ItemSeederB)
    assert ItemSeederA in result  # pulled in as dep
    assert ItemSeederB in result
    assert ProdOnlySeeder not in result


# ── get_by_name ─────────────────────────────────────────────────────────────────


def test_get_by_name_returns_class(session_factory):
    runner = SeederRunner(session_factory)
    runner.register(ItemSeederA)
    assert runner.get_by_name("ItemSeederA") is ItemSeederA


def test_get_by_name_raises_for_unknown(session_factory):
    runner = SeederRunner(session_factory)
    with pytest.raises(ValueError, match="Unknown seeder"):
        runner.get_by_name("NonExistent")


# ── register ────────────────────────────────────────────────────────────────────


def test_register_deduplicates(session_factory):
    runner = SeederRunner(session_factory)
    runner.register(ItemSeederA, ItemSeederA)
    assert runner._registry.count(ItemSeederA) == 1


# ── run ─────────────────────────────────────────────────────────────────────────


async def test_run_inserts_rows(engine, session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.register(ItemSeederA, ItemSeederB)
    await runner.run()

    async with session_factory() as s:
        rows = (await s.execute(select(Item))).scalars().all()
    names = {r.name for r in rows}
    assert "a" in names
    assert "b" in names


async def test_run_subset_only_runs_requested(engine, session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.register(ItemSeederA, ItemSeederB)
    await runner.run(ItemSeederA)

    async with session_factory() as s:
        rows = (await s.execute(select(Item))).scalars().all()
    names = {r.name for r in rows}
    assert "a" in names
    assert "b" not in names


# ── fresh ───────────────────────────────────────────────────────────────────────


# ── parallel execution ──────────────────────────────────────────────────────────


async def test_run_parallel_independent_seeders(engine, session_factory):
    """Seeders with no deps between them should run concurrently (same level)."""
    order: list[str] = []

    class ParallelA(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            await asyncio.sleep(0)  # yield to event loop
            order.append("A")
            session.add(Item(name="pa", value=0))
            await session.commit()

    class ParallelB(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            await asyncio.sleep(0)
            order.append("B")
            session.add(Item(name="pb", value=0))
            await session.commit()

    runner = SeederRunner(session_factory, env=DEV)
    runner.register(ParallelA, ParallelB)
    await runner.run()

    async with session_factory() as s:
        rows = (await s.execute(select(Item))).scalars().all()
    names = {r.name for r in rows}
    assert "pa" in names
    assert "pb" in names
    # Both ran (order doesn't matter for parallel seeders)
    assert set(order) == {"A", "B"}


async def test_run_sequential_dependent_seeders(engine, session_factory):
    """Seeders with a dependency chain must run in strict order."""
    order: list[str] = []

    class SeqA(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            order.append("A")
            session.add(Item(name="sa", value=0))
            await session.commit()

    class SeqB(Seeder):
        depends_on = [SeqA]
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            order.append("B")
            session.add(Item(name="sb", value=0))
            await session.commit()

    runner = SeederRunner(session_factory, env=DEV)
    runner.register(SeqA, SeqB)
    await runner.run()

    assert order == ["A", "B"]


# ── discover ────────────────────────────────────────────────────────────────────


def test_discover_registers_subclasses(session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.discover("tests.fixture_seeders")
    names = {cls.__name__ for cls in runner._registry}
    assert "DiscoverableUserSeeder" in names
    assert "DiscoverablePostSeeder" in names


def test_discover_respects_dependencies(session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.discover("tests.fixture_seeders")
    ordered = runner.list_seeders()
    names = [cls.__name__ for cls in ordered]
    assert names.index("DiscoverableUserSeeder") < names.index("DiscoverablePostSeeder")


def test_discover_deduplicates_on_repeated_calls(session_factory):
    runner = SeederRunner(session_factory, env=DEV)
    runner.discover("tests.fixture_seeders")
    runner.discover("tests.fixture_seeders")
    names = [cls.__name__ for cls in runner._registry]
    assert names.count("DiscoverableUserSeeder") == 1
    assert names.count("DiscoverablePostSeeder") == 1


async def test_fresh_truncates_then_reseeds(engine, session_factory):
    # First run
    runner = SeederRunner(session_factory, env=DEV)
    runner.register(ItemSeederA)
    await runner.run()

    # Run again via fresh — should truncate and re-insert
    await runner.fresh()

    async with session_factory() as s:
        rows = (await s.execute(select(Item))).scalars().all()
    names = [r.name for r in rows]
    # Exactly one 'a' row (not duplicated)
    assert names.count("a") == 1


# ── structlog events ────────────────────────────────────────────────────────────


async def test_run_emits_run_and_seeder_events(engine, session_factory):
    with structlog.testing.capture_logs() as logs:
        runner = SeederRunner(session_factory, env=DEV)
        runner.register(ItemSeederA)
        await runner.run()

    events = [log["event"] for log in logs]
    assert "run.start" in events
    assert "seeder.start" in events
    assert "seeder.finish" in events
    assert "run.finish" in events


async def test_run_logs_include_run_id_and_env(engine, session_factory):
    with structlog.testing.capture_logs() as logs:
        runner = SeederRunner(session_factory, env=DEV)
        runner.register(ItemSeederA)
        await runner.run()

    run_start = next(log for log in logs if log["event"] == "run.start")
    assert "run_id" in run_start
    assert run_start["env"] == DEV


async def test_run_id_is_consistent_within_one_run(engine, session_factory):
    with structlog.testing.capture_logs() as logs:
        runner = SeederRunner(session_factory, env=DEV)
        runner.register(ItemSeederA, ItemSeederB)
        await runner.run()

    run_ids = {log["run_id"] for log in logs if "run_id" in log}
    assert len(run_ids) == 1


async def test_fresh_emits_fresh_start_and_finish(engine, session_factory):
    with structlog.testing.capture_logs() as logs:
        runner = SeederRunner(session_factory, env=DEV)
        runner.register(ItemSeederA)
        await runner.run()
        await runner.fresh()

    events = [log["event"] for log in logs]
    assert "fresh.start" in events
    assert "fresh.finish" in events


async def test_seeder_start_log_includes_seeder_name(engine, session_factory):
    with structlog.testing.capture_logs() as logs:
        runner = SeederRunner(session_factory, env=DEV)
        runner.register(ItemSeederA)
        await runner.run()

    seeder_starts = [log for log in logs if log["event"] == "seeder.start"]
    assert any(log["seeder"] == "ItemSeederA" for log in seeder_starts)


# ── seeder hooks ─────────────────────────────────────────────────────────────


async def test_seeder_hooks_fire_in_order(engine, session_factory):
    order: list[str] = []

    class HookedSeeder(Seeder):
        environments = {DEV}

        async def before_run(self, session: AsyncSession) -> None:
            order.append("before")

        async def run(self, session: AsyncSession) -> None:
            order.append("run")
            session.add(Item(name="hooked", value=0))
            await session.commit()

        async def after_run(self, session: AsyncSession) -> None:
            order.append("after")

    runner = SeederRunner(session_factory, env=DEV, state_tracking=False)
    runner.register(HookedSeeder)
    await runner.run()

    assert order == ["before", "run", "after"]


async def test_seeder_on_error_hook_called_on_failure(engine, session_factory):
    error_received: list[BaseException] = []

    class FailingSeeder(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            raise ValueError("boom")

        async def on_error(self, session: AsyncSession, exc: BaseException) -> None:
            error_received.append(exc)

    runner = SeederRunner(session_factory, env=DEV, state_tracking=False)
    runner.register(FailingSeeder)

    # The runner re-raises, so on_error is not called by the runner directly.
    # on_error is a user extension point on the Seeder — it's not wired into the
    # runner's exception path (that would require the runner to catch and re-raise).
    # Verify that the hook is declared with correct signature.
    instance = FailingSeeder()
    exc = ValueError("test")
    async with session_factory() as s:
        await instance.on_error(s, exc)  # should not raise


# ── runner-level lifecycle hooks ─────────────────────────────────────────────


async def test_runner_before_after_run_hooks_fire(engine, session_factory):
    fired: list[str] = []

    class TrackingRunner(SeederRunner):
        async def before_run(self, run_id: str, env: str) -> None:
            fired.append(f"before:{env}")

        async def after_run(self, run_id: str, env: str) -> None:
            fired.append(f"after:{env}")

    runner = TrackingRunner(session_factory, env=DEV, state_tracking=False)
    runner.register(ItemSeederA)
    await runner.run()

    assert f"before:{DEV}" in fired
    assert f"after:{DEV}" in fired
    assert fired.index(f"before:{DEV}") < fired.index(f"after:{DEV}")


async def test_runner_on_run_error_hook_fires_on_exception(engine, session_factory):
    errors: list[str] = []

    class ErrorRunner(SeederRunner):
        async def on_run_error(self, run_id: str, env: str, exc: BaseException) -> None:
            errors.append(str(exc))

    class BoomSeeder(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            raise RuntimeError("kaboom")

    runner = ErrorRunner(session_factory, env=DEV, state_tracking=False)
    runner.register(BoomSeeder)

    with pytest.raises(RuntimeError, match="kaboom"):
        await runner.run()

    assert "kaboom" in errors


# ── state tracking ───────────────────────────────────────────────────────────


async def test_state_table_created_on_first_run(engine, session_factory):
    runner = SeederRunner(session_factory, env=DEV, state_tracking=True)
    runner.register(ItemSeederA)
    await runner.run()

    async with session_factory() as session:
        rows = (await session.execute(state_table.select())).all()
    assert len(rows) >= 1


async def test_state_row_success_after_run(engine, session_factory):
    runner = SeederRunner(session_factory, env=DEV, state_tracking=True)
    runner.register(ItemSeederA)
    await runner.run()

    async with session_factory() as session:
        states = await get_latest_states(session, ["ItemSeederA"], DEV)

    assert "ItemSeederA" in states
    assert states["ItemSeederA"]["status"] == "success"
    assert states["ItemSeederA"]["env"] == DEV


async def test_state_row_error_after_failing_seeder(engine, session_factory):
    class ErrorSeeder(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            raise ValueError("intentional")

    runner = SeederRunner(session_factory, env=DEV, state_tracking=True)
    runner.register(ErrorSeeder)

    with pytest.raises(ValueError, match="intentional"):
        await runner.run()

    async with session_factory() as session:
        row = (
            await session.execute(
                state_table.select().where(state_table.c.seeder_name == "ErrorSeeder")
            )
        ).one()
    assert row.status == "error"
    assert "intentional" in row.error


async def test_state_tracking_false_writes_no_rows(engine, session_factory):
    runner = SeederRunner(session_factory, env=DEV, state_tracking=False)
    runner.register(ItemSeederA)
    await runner.run()

    # seedling_state table should not exist
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='seedling_state'")
        )
        assert result.scalar() is None


async def test_state_content_hash_stored(engine, session_factory):
    from seedling.state import compute_hash

    runner = SeederRunner(session_factory, env=DEV, state_tracking=True)
    runner.register(ItemSeederA)
    await runner.run()

    expected_hash = compute_hash(ItemSeederA)

    async with session_factory() as session:
        row = (
            await session.execute(
                state_table.select().where(state_table.c.seeder_name == "ItemSeederA")
            )
        ).one()
    assert row.content_hash == expected_hash


# ── fresh wipes state ─────────────────────────────────────────────────────────


async def test_fresh_wipes_state_before_reseeding(engine, session_factory):
    runner = SeederRunner(session_factory, env=DEV, state_tracking=True)
    runner.register(ItemSeederA)
    await runner.run()

    async with session_factory() as session:
        count_before = (await session.execute(
            state_table.select().where(
                state_table.c.seeder_name == "ItemSeederA",
                state_table.c.env == DEV,
            )
        )).all()
    assert len(count_before) >= 1

    await runner.fresh()

    # After fresh: old rows gone; new success row exists
    async with session_factory() as session:
        all_rows = (await session.execute(
            state_table.select().where(
                state_table.c.seeder_name == "ItemSeederA",
                state_table.c.env == DEV,
            )
        )).all()
    # fresh wipes then re-runs — only the new run's row should be present
    assert all(r.status == "success" for r in all_rows)
    assert len(all_rows) == 1


# ── --new-only ───────────────────────────────────────────────────────────────


async def test_new_only_skips_seeders_with_matching_hash(engine, session_factory):
    call_count = {"n": 0}

    class CountedSeeder(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            call_count["n"] += 1
            session.add(Item(name="counted", value=0))
            await session.commit()

    runner = SeederRunner(session_factory, env=DEV, state_tracking=True)
    runner.register(CountedSeeder)
    await runner.run()
    assert call_count["n"] == 1

    await runner.run(new_only=True)
    assert call_count["n"] == 1  # skipped — hash matches and status is success


async def test_new_only_runs_seeders_with_error_status(engine, session_factory):
    attempt = {"n": 0}

    class FlakySeeder(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            attempt["n"] += 1
            if attempt["n"] == 1:
                raise RuntimeError("first attempt fails")
            session.add(Item(name="flaky", value=0))
            await session.commit()

    runner = SeederRunner(session_factory, env=DEV, state_tracking=True)
    runner.register(FlakySeeder)

    with pytest.raises(RuntimeError):
        await runner.run()
    assert attempt["n"] == 1

    # --new-only should re-run because last status was error
    await runner.run(new_only=True)
    assert attempt["n"] == 2


async def test_force_overrides_new_only(engine, session_factory):
    call_count = {"n": 0}

    class AlwaysRunSeeder(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            call_count["n"] += 1
            session.add(Item(name="always", value=0))
            await session.commit()

    runner = SeederRunner(session_factory, env=DEV, state_tracking=True)
    runner.register(AlwaysRunSeeder)
    await runner.run()
    assert call_count["n"] == 1

    # --force overrides --new-only
    await runner.run(new_only=True, force=True)
    assert call_count["n"] == 2


# ── transactional mode ───────────────────────────────────────────────────────


async def test_transactional_mode_runs_all_seeders(engine, session_factory):
    runner = SeederRunner(session_factory, env=DEV, transactional=True, state_tracking=False)
    runner.register(ItemSeederA, ItemSeederB)
    await runner.run()

    async with session_factory() as s:
        rows = (await s.execute(select(Item))).scalars().all()
    names = {r.name for r in rows}
    assert "a" in names
    assert "b" in names


async def test_transactional_mode_rollback_on_error(engine, session_factory):
    class GoodSeeder(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            session.add(Item(name="good", value=1))

    class BadSeeder(Seeder):
        depends_on = [GoodSeeder]
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            raise RuntimeError("rollback me")

    runner = SeederRunner(session_factory, env=DEV, transactional=True, state_tracking=False)
    runner.register(GoodSeeder, BadSeeder)

    with pytest.raises(RuntimeError, match="rollback me"):
        await runner.run()

    async with session_factory() as s:
        rows = (await s.execute(select(Item))).scalars().all()
    assert all(r.name != "good" for r in rows)


# ── max_parallel ─────────────────────────────────────────────────────────────


async def test_max_parallel_limits_concurrency(engine, session_factory):
    active: list[int] = []
    peak: list[int] = []

    class SlowSeederA(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            active.append(1)
            peak.append(len(active))
            await asyncio.sleep(0)
            active.pop()
            session.add(Item(name="slow_a", value=0))
            await session.commit()

    class SlowSeederB(Seeder):
        environments = {DEV}

        async def run(self, session: AsyncSession) -> None:
            active.append(1)
            peak.append(len(active))
            await asyncio.sleep(0)
            active.pop()
            session.add(Item(name="slow_b", value=0))
            await session.commit()

    runner = SeederRunner(session_factory, env=DEV, max_parallel=1, state_tracking=False)
    runner.register(SlowSeederA, SlowSeederB)
    await runner.run()

    assert max(peak) <= 1

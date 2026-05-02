# Benchmarks

All benchmarks run against an in-memory SQLite database on a single machine.
SQLite has no network latency, so the absolute numbers are faster than a real
PostgreSQL instance — but the **relative speedups are conservative**. Against
a networked database the bulk insert and parallel execution gains are larger
because each per-row round-trip carries real latency.

To reproduce locally:

```bash
uv run python benchmarks/bench_create_batch.py --rows 1000
uv run python benchmarks/bench_parallel.py
```

---

## Bulk insert: `create_batch(bulk=True)`

`create_batch(bulk=True)` uses a single `INSERT ... RETURNING` statement
instead of N per-row `add` + `flush` calls.

| Rows | Per-row | Bulk | Speedup |
|-----:|--------:|-----:|--------:|
| 100 | 0.044s | 0.006s | **7.3x** |
| 1 000 | 0.412s | 0.055s | **7.6x** |
| 5 000 | 2.116s | 0.278s | **7.6x** |

The speedup stabilises around **7–8x** and holds linearly — bulk insert scales
at ~18 000 rows/s vs ~2 400 rows/s per-row on SQLite. The gap widens further
on PostgreSQL where each round-trip carries network overhead.

**When to use `bulk=True`:** any batch larger than a few hundred rows where
you don't need `@post_generation` hooks or `RelatedFactory` to fire.

---

## Parallel level execution

Independent seeders (no `depends_on` relationship) run concurrently via
`asyncio.gather`. The benchmark uses three seeders: Alpha and Beta run in
parallel, then Gamma runs after both complete.

| Mode | Time | Notes |
|------|-----:|-------|
| Parallel (default) | 0.219s | Alpha + Beta concurrent |
| Sequential (`max_parallel=1`) | 0.245s | Alpha → Beta → Gamma |

The SQLite in-memory numbers show only a modest gain because SQLite
serialises writes internally. Against PostgreSQL the parallel advantage grows
proportionally with the number of independent seeders and their individual
durations — two 5-second seeders that run in parallel take 5s instead of 10s.

---

## Tracking over time

Benchmark results are recorded automatically on every push to `main` and
displayed as a time-series chart on the
[GitHub Pages benchmark dashboard](https://arthurvasconcelos.github.io/seedling/dev/bench/).

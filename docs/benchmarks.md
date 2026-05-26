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
uv run python benchmarks/bench_vs_alternatives.py --rows 1000

# PostgreSQL via testcontainers (requires Docker)
uv run python benchmarks/bench_vs_alternatives.py --postgres --rows 500
```

---

## vs raw SQLAlchemy and factory_boy

Same scenario in every row: insert N records into a single table with a string
column and an int column, against a fresh in-memory SQLite database.
Both Seedling and factory_boy use `Sequence`-based field generators for an
apples-to-apples comparison.

| Scenario | 1 000 rows | rows/s | vs raw bulk |
|---|---:|---:|---:|
| raw SQLAlchemy (bulk insert) | 0.002s | 520 000 | **1.0x** (floor) |
| Seedling `create_batch(bulk=True)` | 0.011s | 90 000 | 6x |
| factory_boy (sync) | 0.060s | 16 700 | 31x |
| raw SQLAlchemy (per-row `add`) | 0.122s | 8 200 | 63x |
| Seedling `create_batch()` (per-row) | 0.127s | 7 900 | 66x |

Three honest takeaways:

- **Bulk mode is fastest.** Seedling's `create_batch(bulk=True)` uses a single
  `INSERT … RETURNING` statement and now outperforms factory_boy by ~5x.
- **Per-row mode now matches raw SQLAlchemy.** The 1.0.0 fast lane batches all
  flush/refresh work into a single round-trip for factories without
  `@post_generation` hooks or `RelatedFactory` descriptors. The remaining gap
  vs raw is Python-level factory overhead.
- **Hooks and related factories use the legacy per-row loop automatically.**
  No configuration needed — Seedling detects the presence of hooks at class
  definition time and routes accordingly.

factory_boy is measured against a sync engine because that's how it is
actually used; the wall-clock number is what an async-app author experiences
if they reach for that library.

See the [Performance guide](/performance) for a deeper explanation of which
code path fires and how to tune it.

---

## Bulk insert: `create_batch(bulk=True)`

`create_batch(bulk=True)` uses a single `INSERT ... RETURNING` statement
instead of N per-row `add` + `flush` calls.

| Rows | Per-row | Bulk | Speedup |
|-----:|--------:|-----:|--------:|
| 100 | 0.019s | 0.006s | **3.1x** |
| 1 000 | 0.177s | 0.053s | **3.3x** |
| 5 000 | 0.872s | 0.267s | **3.3x** |

These numbers use `AutoFactory` with smart defaults (Faker). Because the fast lane
already reduces per-row to a single flush, the bulk speedup is now ~3× rather than
the 7–8× seen in 0.x releases. Use `Sequence`-based factories (or
`Meta: smart_defaults = False`) to push per-row throughput to ~8 000 rows/s, at
which point bulk is still ~10× faster for large batches. The gap widens further on
PostgreSQL where each round-trip carries network overhead.

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

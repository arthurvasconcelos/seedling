---
url: /seedling/v1.0.0/performance.md
---
# Performance guide

Seedling exposes three factory code paths with very different cost profiles.
Understanding which one runs — and when — lets you tune test-suite speed without
changing the API.

***

## The three paths

### Bulk path — `create_batch(bulk=True)`

A single `INSERT … RETURNING` statement inserts all rows in one database
round-trip. Post-generation hooks and related factories **do not fire**;
SubFactory / FK fields are skipped (you must supply them via overrides).

Use this for large seed data where you control all field values and have no
need for relational side-effects.

```python
items = await ItemFactory.create_batch(session, 5_000, bulk=True)
```

**Throughput (1 000 rows, SQLite):** ~90 000 rows/s

***

### Auto-fast path — `create_batch()` default, plain factory

When `create_batch(session, n)` is called without `bulk=True`, Seedling
automatically checks whether the factory qualifies for the fast lane:

* no `@post_generation` hooks
* no `RelatedFactory` / `RelatedFactoryList` descriptors
* no `SubFactory` or FK-auto-resolve fields

If all three conditions hold, Seedling builds all `n` field dicts, calls
`session.add_all(instances)`, and **flushes once**, matching the throughput of
raw `session.add()` loops. The check result is cached on the factory class so
the decision costs nothing after the first call.

```python
# Plain factory, no hooks, no relations → fast lane fires automatically
items = await ItemFactory.create_batch(session, 1_000)
```

**Throughput (1 000 rows, SQLite):** ~8 000 rows/s — on par with raw
`session.add()` + single flush.

**Behaviour note:** `before_flush` / `after_flush` session events fire **once
per batch**, not once per row, when the fast lane is active. Factories with
hooks or related factories are unaffected.

***

### Slow path — per-row loop

Used automatically whenever the fast lane is not eligible: hooks, related
factories, or SubFactory fields are declared.

Each row goes through a full `create()` cycle — field resolution, flush, and
conditional refresh — so hooks receive the live, flushed instance before the
next row starts.

```python
class UserFactory(Factory[User]):
    model = User
    name = Sequence(lambda n: f"user-{n}")

    @post_generation
    async def create_profile(instance, session):
        await ProfileFactory.create(session, user_id=instance.id)


# @post_generation declared → slow path, fires per row
users = await UserFactory.create_batch(session, 50)
```

**Throughput (1 000 rows, SQLite):** ~2 400 rows/s

***

## Refresh skip

After every `flush()`, Seedling checks whether the model has any server-side
column defaults (`server_default`, `server_onupdate`, or `Computed` columns).
If none exist, the `refresh()` SELECT is skipped entirely — SQLAlchemy already
populated the primary key from `cursor.lastrowid` or the `RETURNING` clause.

The inspection result is **cached per factory class** on first access.

```python
# No server_default → refresh skipped, PK populated from lastrowid
item = await ItemFactory.create(session)
assert item.id is not None  # ✓, no extra SELECT needed
```

If your model does have a server-side default (e.g. `CURRENT_TIMESTAMP`,
`uuid_generate_v4()`, or a generated column), the refresh fires automatically
— you do not need to configure anything.

***

## Smart defaults and throughput

`AutoFactory` uses [Faker](https://faker.readthedocs.io/) to generate realistic
values for columns whose names match common patterns (`name`, `email`, `city`,
…). Each Faker call costs roughly **45 µs**. For throughput-sensitive code this
adds up:

| Setup | rows/s |
|---|---:|
| `AutoFactory` with smart defaults (Faker for `name` column) | ~5 600 |
| `AutoFactory` or `Factory` with `Sequence`-based fields | ~8 000 |

If you are inserting thousands of rows in a test and do not need realistic-
looking strings, override the slow columns with a `Sequence`:

```python
class ItemFactory(AutoFactory[Item]):
    model = Item
    name = Sequence(lambda n: f"item-{n}")  # bypasses Faker
```

Or disable smart defaults entirely for the whole factory:

```python
class ItemFactory(AutoFactory[Item]):
    model = Item

    class Meta:
        smart_defaults = False
```

***

## Decision guide

| Scenario | Recommended path |
|---|---|
| Seed data, thousands of rows, no hooks needed | `bulk=True` |
| Test data, no hooks / relations, want real IDs | default (`bulk=False`) — auto-fast lane |
| Test data, `@post_generation` or `RelatedFactory` needed | default — slow path fires automatically |
| Throughput matters, `name` column in model | add `name = Sequence(...)` override |

***

## Running the benchmark

```bash
# SQLite (in-memory, fast, no Docker needed)
uv run python benchmarks/bench_vs_alternatives.py --rows 1000

# PostgreSQL via testcontainers (requires Docker)
uv run python benchmarks/bench_vs_alternatives.py --postgres --rows 500
```

See [Benchmarks](/benchmarks) for recorded numbers and methodology notes.

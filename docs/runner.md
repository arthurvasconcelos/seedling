# Runner

`SeederRunner` orchestrates seeder execution: dependency resolution, environment filtering, parallel execution, and state tracking.

## Creating a runner

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from seedling import SeederRunner

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/mydb")
session_factory = async_sessionmaker(engine, expire_on_commit=False)

runner = SeederRunner(session_factory, env="development")
```

### Constructor parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `session_factory` | `async_sessionmaker` | required | SQLAlchemy async session factory |
| `env` | `str` | `"development"` | Environment string passed to environment filters |
| `state_tracking` | `bool` | `True` | Record executions in `seedling_state` table |
| `transactional` | `bool` | `False` | Wrap the entire run in a single transaction |
| `max_parallel` | `int \| None` | `None` | Cap concurrency within a dependency level |

## Registering seeders

Register explicitly:

```python
runner.register(UserSeeder, PostSeeder, CommentSeeder)
```

Or discover all seeders in a package automatically:

```python
runner.discover("myapp.seeders")
```

`discover()` imports every module under the package and registers all `Seeder` subclasses it finds. Calling it multiple times is safe — duplicates are ignored.

## Running seeders

```python
await runner.run()                       # run all seeders for the current env
await runner.run(PostSeeder)             # run PostSeeder + its dependencies
await runner.run(new_only=True)          # skip seeders whose source hash matches latest success
await runner.run(force=True)            # override new_only — always run all
await runner.run(tags={"demo"})         # only run seeders tagged "demo"
```

Seeders at the same dependency level run concurrently via `asyncio.gather`. Dependent seeders always run after their dependencies.

### `run()` parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `*seeder_classes` | `type[Seeder]` | — | Optional subset; defaults to all registered |
| `new_only` | `bool` | `False` | Skip seeders with matching state hash |
| `force` | `bool` | `False` | Override `new_only` — run regardless of state |
| `tags` | `set[str] \| None` | `None` | Filter to seeders whose `tags` intersects this set |

## Fresh (truncate + reseed)

```python
await runner.fresh()                     # truncate all then reseed
await runner.fresh(PostSeeder)           # truncate + reseed PostSeeder and its deps
await runner.fresh(tags={"demo"})        # only fresh seeders tagged "demo"
```

Tables are truncated in reverse dependency order, then re-seeded in forward order. `seed fresh` also wipes `seedling_state` rows for affected seeders before truncating (clean-slate semantics).

## Listing seeders

```python
ordered = runner.list_seeders()                        # all, env-filtered, sorted
subset  = runner.list_seeders(PostSeeder)              # PostSeeder + dependencies
tagged  = runner.list_seeders(tags={"smoke"})          # only tagged seeders
```

Returns a flat list — no execution happens.

## Transactional mode

`transactional=True` wraps the entire run in a single transaction. All seeders share one session; if any seeder raises, everything rolls back.

```python
runner = SeederRunner(session_factory, env="test", transactional=True)
await runner.run()
```

**Note:** State tracking is skipped in transactional mode — if the transaction rolled back, any state rows would roll back too, making them unreliable. Use transactional mode for test isolation, not production audit.

## Parallel cap

```python
runner = SeederRunner(session_factory, env="development", max_parallel=4)
```

By default all seeders within a dependency level run in parallel. `max_parallel` caps how many run simultaneously within each level.

## Exporting and restoring data

```python
data = await runner.export()
# {"users": [{"id": 1, "email": "..."}, ...], "posts": [...]}

total = await runner.restore(data)   # returns total rows inserted
```

Only models declared on `Seeder.models` are exported. The restore path uses bulk Core insert; table order must satisfy FK constraints (export order is safe to restore as-is).

## Lookup by name

```python
cls = runner.get_by_name("UserSeeder")   # raises ValueError for unknown names
```

## Runner-level lifecycle hooks

Override these async methods on a `SeederRunner` subclass to react to run-level events:

```python
class AuditingRunner(SeederRunner):
    async def before_run(self, run_id: str, env: str) -> None:
        print(f"run {run_id} starting for {env}")

    async def after_run(self, run_id: str, env: str) -> None:
        print(f"run {run_id} complete")

    async def on_run_error(self, run_id: str, env: str, exc: BaseException) -> None:
        print(f"run {run_id} failed: {exc}")
```

All three are no-ops by default. `on_run_error` does not suppress the exception.

## pytest fixture

The `seedling_runner` fixture is provided by the pytest plugin:

```python
# conftest.py
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

@pytest.fixture(scope="session")
def seedling_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    return async_sessionmaker(engine, expire_on_commit=False)

# test_something.py
async def test_with_users(seedling_runner):
    await seedling_runner.run(UserSeeder)
    ...
```

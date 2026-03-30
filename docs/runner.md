# Runner

`SeederRunner` orchestrates seeder execution: dependency resolution, environment filtering, and parallel execution.

## Creating a runner

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from seedling import SeederRunner

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/mydb")
session_factory = async_sessionmaker(engine, expire_on_commit=False)

runner = SeederRunner(session_factory, env="development")
```

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
await runner.run()              # run all seeders for the current env
await runner.run(PostSeeder)    # run PostSeeder + its dependencies
```

Seeders at the same dependency level run concurrently via `asyncio.gather`. Dependent seeders always run after their dependencies.

## Fresh (truncate + reseed)

```python
await runner.fresh()            # truncate all then reseed
await runner.fresh(PostSeeder)  # truncate + reseed PostSeeder and its deps
```

Tables are truncated in reverse dependency order, then re-seeded in forward order.

## Listing seeders

```python
ordered = runner.list_seeders()          # all, env-filtered, topologically sorted
subset = runner.list_seeders(PostSeeder) # PostSeeder + dependencies
```

Returns a flat list — no execution happens.

## Exporting data

```python
data = await runner.export()
# {"users": [{"id": 1, "email": "..."}, ...], "posts": [...]}
```

Only models declared on `Seeder.models` are exported. Returns a dict keyed by table name.

## Lookup by name

```python
cls = runner.get_by_name("UserSeeder")
```

Raises `ValueError` for unknown names.

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

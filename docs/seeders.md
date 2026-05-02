# Seeders

A `Seeder` is a class that populates one or more database tables. Seeders declare their dependencies so the runner can resolve execution order and parallelise independent seeders.

## Defining a seeder

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from seedling import Seeder, DEV_AND_TEST
from myapp.models import User

class UserSeeder(Seeder):
    environments = DEV_AND_TEST
    models = [User]

    async def run(self, session: AsyncSession) -> None:
        session.add(User(email="alice@example.com", name="Alice"))
        await session.commit()

    async def truncate(self, session: AsyncSession) -> None:
        await session.execute(text("TRUNCATE users CASCADE"))
```

## Class variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `depends_on` | `list[type[Seeder]]` | `[]` | Seeders that must run before this one |
| `environments` | `set[str]` | `DEV_AND_TEST` | Environments in which this seeder runs |
| `idempotent` | `bool` | `True` | Whether `upsert()` uses `on_conflict_do_nothing` |
| `models` | `list[Any]` | `[]` | ORM model classes seeded here (used by `seed export`) |
| `tags` | `set[str]` | `set()` | Arbitrary labels for tag-based filtering |

## Dependency ordering

Use `depends_on` to declare that one seeder requires another to have run first:

```python
class PostSeeder(Seeder):
    depends_on = [UserSeeder]

    async def run(self, session: AsyncSession) -> None:
        ...
```

The runner resolves a topological sort and executes independent seeders concurrently at each level.

## Environments

Environment constants are provided by seedling:

```python
from seedling import DEV, TEST, PROD, ALL, DEV_AND_TEST
```

Only seeders whose `environments` set contains the current env are executed. Use `--env` on the CLI to select the environment.

```python
class ProdSeeder(Seeder):
    environments = {PROD}  # only runs with: seed run --env production
```

## Tags

Tag seeders with arbitrary labels for fine-grained filtering:

```python
class UserSeeder(Seeder):
    environments = DEV_AND_TEST
    tags = {"demo", "smoke"}

class HeavySeeder(Seeder):
    environments = DEV_AND_TEST
    tags = {"demo"}
```

```bash
seed run --tag smoke          # only runs UserSeeder (it has the "smoke" tag)
seed run --tag demo           # runs both
seed run --tag demo --tag smoke  # union: runs any seeder matching either tag
```

Tags filter independently from the environment filter — both must pass for a seeder to run.

## Auto-discovery

Instead of manually registering seeders, call `runner.discover()` with your seeders package:

```python
runner.discover("myapp.seeders")
```

This imports all modules under the package and registers every `Seeder` subclass it finds.

## Lifecycle hooks

Override these async methods to add logic before or after a seeder runs:

```python
class UserSeeder(Seeder):
    environments = DEV_AND_TEST

    async def before_run(self, session: AsyncSession) -> None:
        # Called immediately before run()
        pass

    async def run(self, session: AsyncSession) -> None:
        ...

    async def after_run(self, session: AsyncSession) -> None:
        # Called after a successful run()
        pass

    async def on_error(self, session: AsyncSession, exc: BaseException) -> None:
        # Called if run() raises — default is a no-op
        pass
```

All hooks are no-ops by default. `on_error` receives the exception but does not suppress it — the runner still re-raises after calling it.

# sqlalchemy-seedling

Async-native seeder and factory library for SQLAlchemy.

## Installation

```bash
pip install sqlalchemy-seedling
# or with uv
uv add sqlalchemy-seedling
```

Optional YAML fixture support:

```bash
pip install sqlalchemy-seedling[yaml]
```

## 5-minute quickstart

### 1. Scaffold the layout

```bash
seed init
```

Creates `seeders/` and `factories/` packages and appends a `[tool.seedling]` block to `pyproject.toml`.

### 2. Configure your runner

Point the CLI at your runner factory in `pyproject.toml`:

```toml
[tool.seedling]
runner = "myapp.seeders:create_runner"
```

### 3. Create a runner factory

```python
# myapp/seeders/__init__.py
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from seedling import SeederRunner

def create_runner(env: str) -> SeederRunner:
    engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/mydb")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    runner = SeederRunner(session_factory, env=env)
    runner.discover("myapp.seeders")
    return runner
```

### 4. Write a seeder

```python
# myapp/seeders/users.py
from seedling import Seeder, DEV_AND_TEST
from sqlalchemy.ext.asyncio import AsyncSession
from myapp.models import User

class UserSeeder(Seeder):
    environments = DEV_AND_TEST
    models = [User]
    tags = {"demo"}

    async def run(self, session: AsyncSession) -> None:
        session.add(User(email="admin@example.com", name="Admin"))
        await session.commit()

    async def truncate(self, session: AsyncSession) -> None:
        await session.execute(text("TRUNCATE users CASCADE"))
```

### 5. Run it

```bash
seed run          # run all seeders for development
seed fresh        # truncate then re-seed
seed list         # show execution order
seed status       # show last run per seeder + drift detection
seed export       # dump seeded rows to fixtures.json
```

## What's included

| Feature | Description |
|---------|-------------|
| `Seeder` | Base class with `depends_on`, `environments`, `models`, `tags`, and lifecycle hooks |
| `SeederRunner` | Orchestrates parallel execution, state tracking, and transactional mode |
| `Factory[T]` | Build and persist ORM objects with traits, descriptors, and hooks |
| `AutoFactory[T]` | Mapper-introspected factory with smart name-based defaults |
| `upsert()` | Dialect-aware idempotent insert helper |
| `truncate_tables()` | Dialect-aware TRUNCATE (PG cascade, MariaDB FK disable, SQLite DELETE) |
| `reset_sequences()` | Reset PostgreSQL SERIAL/IDENTITY sequences after truncation |
| `deferred_constraints()` | Defer FK constraints for the duration of a block (PostgreSQL) |
| `seed` CLI | Full command set: `run`, `fresh`, `list`, `status`, `validate`, `graph`, `export`, `restore`, `init`, `make:seeder`, `make:factory` |
| pytest plugin | `seedling_runner`, `seedling_transactional_session`, and `@seed()` fixtures |
| State tracking | `seedling_state` table: audit log, drift detection, `--new-only` skip |

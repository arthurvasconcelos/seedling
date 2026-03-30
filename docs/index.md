# sqlalchemy-seedling

Async-native seeder and factory library for SQLAlchemy.

## Installation

```bash
pip install sqlalchemy-seedling
# or with uv
uv add sqlalchemy-seedling
```

## 5-minute quickstart

### 1. Configure your runner

Add a `[tool.seedling]` section to `pyproject.toml`:

```toml
[tool.seedling]
runner = "myapp.seeders:create_runner"
```

### 2. Create a runner factory

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

### 3. Write a seeder

```python
# myapp/seeders/users.py
from seedling import Seeder, DEV_AND_TEST
from sqlalchemy.ext.asyncio import AsyncSession
from myapp.models import User

class UserSeeder(Seeder):
    environments = DEV_AND_TEST
    models = [User]

    async def run(self, session: AsyncSession) -> None:
        session.add(User(email="admin@example.com", name="Admin"))
        await session.commit()

    async def truncate(self, session: AsyncSession) -> None:
        await session.execute(text("TRUNCATE users CASCADE"))
```

### 4. Run it

```bash
seed run          # run all seeders for development
seed fresh        # truncate then re-seed
seed list         # show execution order
seed export       # dump seeded rows to fixtures.json
```

## What's included

| Feature | Description |
|---------|-------------|
| `Seeder` | Base class with `depends_on`, `environments`, `models` |
| `SeederRunner` | Orchestrates parallel execution via `asyncio.gather` |
| `Factory[T]` | Build and persist ORM objects with traits and sub-factories |
| `upsert()` | Dialect-aware upsert helper for idempotent seeders |
| `seed` CLI | `run`, `fresh`, `list`, `export` commands |
| pytest plugin | `seedling_runner` fixture for seeding in tests |

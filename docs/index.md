---
layout: home

hero:
  name: sqlalchemy-seedling
  text: Async-native seeder & factory library
  tagline: Built for SQLAlchemy 2.0+ async workflows — seed databases, generate fixtures, and run factories without the boilerplate.
  image:
    src: /assets/logo.png
    alt: sqlalchemy-seedling
  actions:
    - theme: brand
      text: Get Started
      link: /seeders
    - theme: alt
      text: View on GitHub
      link: https://github.com/arthurvasconcelos/seedling

features:
  - title: Seeder
    details: Base class with depends_on, environments, models, tags, and lifecycle hooks for ordered, environment-aware seeding.
  - title: Factory & AutoFactory
    details: Build and persist ORM objects with traits, descriptors, and post-generation hooks. AutoFactory introspects the mapper for zero-config defaults.
  - title: SeederRunner
    details: Orchestrates parallel execution, state tracking, and transactional mode across your full seeder graph.
  - title: seed CLI
    details: Full command set — run, fresh, list, status, validate, graph, export, restore, init, make:seeder, make:factory.
  - title: pytest plugin
    details: Drop-in fixtures — seedling_runner, seedling_transactional_session, and @seed() decorator for clean per-test isolation.
  - title: State Tracking
    details: seedling_state audit log with drift detection and --new-only skip so re-runs are fast and idempotent.
---

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

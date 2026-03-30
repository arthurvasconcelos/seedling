# sqlalchemy-seedling

Async-native seeder and factory library for SQLAlchemy.
Dependency-aware runners, declarative factories, and a CLI — Laravel-style ergonomics for the Python async ecosystem.

[![PyPI version](https://img.shields.io/pypi/v/sqlalchemy-seedling)](https://pypi.org/project/sqlalchemy-seedling/)
[![Python versions](https://img.shields.io/pypi/pyversions/sqlalchemy-seedling)](https://pypi.org/project/sqlalchemy-seedling/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/arthurvasconcelos/seedling/actions/workflows/ci.yml/badge.svg)](https://github.com/arthurvasconcelos/seedling/actions)

---

## Why seedling?

- **Dependency-aware** — declare `depends_on` between seeders and the runner resolves the correct execution order automatically (Kahn's topological sort).
- **Async-native** — built for `async`/`await` and SQLAlchemy's async session from the ground up; no sync wrappers.
- **Declarative factories** — `Factory[T]` with `LazyAttribute`, `Sequence`, `SubFactory`, and `as_trait()` for composable test data.
- **Environment filtering** — tag seeders with `environments = {DEV, TEST, PROD}` and the runner skips what doesn't belong.
- **Zero boilerplate CLI** — one line in `pyproject.toml` and you get `seed run`, `seed fresh`, and `seed list`.

---

## Installation

```bash
pip install sqlalchemy-seedling
# or
uv add sqlalchemy-seedling
```

Requires Python 3.11+ and SQLAlchemy 2.0+.

---

## Quick start

### 1. Define seeders

```python
# myapp/seeders/user_seeder.py
from seedling import Seeder, DEV_AND_TEST
from sqlalchemy.ext.asyncio import AsyncSession
from myapp.models import User

class UserSeeder(Seeder):
    environments = DEV_AND_TEST

    async def run(self, session: AsyncSession) -> None:
        session.add(User(email="admin@example.com", name="Admin"))
        await session.commit()

    async def truncate(self, session: AsyncSession) -> None:
        await session.execute(delete(User))
        await session.commit()


# myapp/seeders/post_seeder.py
from seedling import Seeder, DEV_AND_TEST

class PostSeeder(Seeder):
    depends_on = [UserSeeder]       # runs after UserSeeder automatically
    environments = DEV_AND_TEST

    async def run(self, session: AsyncSession) -> None:
        ...
```

### 2. Create a runner factory

```python
# myapp/seeders/__init__.py
from seedling import SeederRunner
from myapp.db import async_session_maker
from myapp.seeders.user_seeder import UserSeeder
from myapp.seeders.post_seeder import PostSeeder

def create_runner(env: str = "development") -> SeederRunner:
    runner = SeederRunner(session_factory=async_session_maker, env=env)
    runner.register(UserSeeder, PostSeeder)
    return runner
```

### 3. Configure the CLI

```toml
# pyproject.toml
[tool.seedling]
runner = "myapp.seeders:create_runner"
```

### 4. Run

```bash
seed run                        # run all seeders for the default env
seed run UserSeeder             # run a specific seeder (+ its dependencies)
seed fresh                      # truncate then re-seed
seed list                       # print execution order without running
seed run --env production       # target a different environment
```

---

## Factories

Use `Factory[T]` to build and persist model instances with minimal boilerplate.

```python
from seedling import Factory, LazyAttribute, Sequence, SubFactory, faker
from myapp.models import User, Post

class UserFactory(Factory[User]):
    model = User
    email = LazyAttribute(lambda f: faker.unique.email())
    name  = Sequence(lambda n: f"User {n}")

class PostFactory(Factory[Post]):
    model = Post
    author = SubFactory(UserFactory)       # creates a User row automatically
    title  = LazyAttribute(lambda f: faker.sentence())
```

```python
# In tests or seeders:
user = await UserFactory.create(session)
posts = await PostFactory.create_batch(session, 5)

# build() never touches the DB — useful in pure unit tests:
user = UserFactory.build(email="test@example.com")

# Traits for scenario-specific variants:
AdminUser = UserFactory.as_trait(is_superuser=True)
admin = await AdminUser.create(session)
```

---

## Helpers

```python
from seedling import upsert

# Idempotent insert — ON CONFLICT DO NOTHING (PostgreSQL) / INSERT OR IGNORE (SQLite)
await upsert(session, MyModel, {"id": 1, "name": "Foo"})
await upsert(session, MyModel, {"id": 1, "name": "Foo"}, constraint="uq_mymodel_name")
```

---

## Environment constants

```python
from seedling import DEV, TEST, PROD, ALL, DEV_AND_TEST
```

| Constant      | Value                              |
|---------------|------------------------------------|
| `DEV`         | `"development"`                    |
| `TEST`        | `"test"`                           |
| `PROD`        | `"production"`                     |
| `DEV_AND_TEST`| `{"development", "test"}`          |
| `ALL`         | `{"development", "test", "production"}` |

---

## License

MIT — see [LICENSE](LICENSE).

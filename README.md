<p align="center">
  <img src="docs/assets/logo.png" width="120" alt="sqlalchemy-seedling logo">
</p>

# sqlalchemy-seedling

Async-native seeder and factory library for SQLAlchemy.
Dependency-aware runners, declarative factories, and a full CLI — designed for the async Python ecosystem.

[![PyPI version](https://img.shields.io/pypi/v/sqlalchemy-seedling)](https://pypi.org/project/sqlalchemy-seedling/)
[![Python versions](https://img.shields.io/pypi/pyversions/sqlalchemy-seedling)](https://pypi.org/project/sqlalchemy-seedling/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/arthurvasconcelos/seedling/actions/workflows/ci.yml/badge.svg)](https://github.com/arthurvasconcelos/seedling/actions)
[![Coverage](https://codecov.io/gh/arthurvasconcelos/seedling/graph/badge.svg)](https://codecov.io/gh/arthurvasconcelos/seedling)
[![Downloads](https://img.shields.io/pypi/dm/sqlalchemy-seedling)](https://pypi.org/project/sqlalchemy-seedling/)

---

## Why seedling?

- **Async-native** — built for `async`/`await` and SQLAlchemy 2.0's async session from day one. No sync wrappers, no thread-pool shims.
- **Dependency-aware** — declare `depends_on` between seeders; the runner topologically sorts them and runs independent seeders in parallel via `asyncio.gather`.
- **Rich factories** — `Factory[T]` with `Faker`, `LazyAttribute`, `Sequence`, `SubFactory`, declarative `Trait` classes, `@post_generation` hooks, and `AutoFactory[T]` for mapper-introspected defaults.
- **State tracking** — every run is recorded in a `seedling_state` table: append-only audit log, drift detection via content hash, and a `--new-only` skip flag.
- **Full CLI** — `seed run`, `seed fresh`, `seed status`, `seed validate`, `seed graph`, `seed export`, `seed restore`, and scaffolding commands.
- **Framework-agnostic** — works with FastAPI, Litestar, or a plain script; no framework coupling.

---

## Installation

```bash
pip install sqlalchemy-seedling
# or
uv add sqlalchemy-seedling
```

Optional YAML fixture support:

```bash
pip install sqlalchemy-seedling[yaml]
```

Requires Python 3.11+ and SQLAlchemy 2.0+.

---

## Quick start

### Scaffold the project layout

```bash
seed init
```

Creates `seeders/` and `factories/` packages and appends `[tool.seedling]` to `pyproject.toml`.

### Define seeders

```python
# seeders/users.py
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


# seeders/posts.py
from seedling import Seeder, DEV_AND_TEST
from seeders.users import UserSeeder

class PostSeeder(Seeder):
    depends_on = [UserSeeder]       # runs after UserSeeder automatically
    environments = DEV_AND_TEST

    async def run(self, session: AsyncSession) -> None:
        ...
```

### Create a runner factory

```python
# seeders/__init__.py
from seedling import SeederRunner
from myapp.db import async_session_maker
from .users import UserSeeder
from .posts import PostSeeder

def create_runner(env: str = "development") -> SeederRunner:
    runner = SeederRunner(session_factory=async_session_maker, env=env)
    runner.register(UserSeeder, PostSeeder)
    return runner
```

### Configure the CLI

```toml
# pyproject.toml
[tool.seedling]
runner = "seeders:create_runner"
```

### Run

```bash
seed run                          # run all seeders for development
seed run --tag demo               # run only seeders tagged "demo"
seed fresh                        # truncate then re-seed
seed status                       # latest run per seeder + drift detection
seed list                         # print execution order without running
```

---

## Factories

```python
from seedling import Factory, Faker, LazyAttribute, Sequence, SubFactory, Trait

class UserFactory(Factory[User]):
    model = User
    email = Faker("email")
    name  = Sequence(lambda n: f"User {n}")

    class admin(Trait):
        is_superuser = True

class PostFactory(Factory[Post]):
    model = Post
    author = SubFactory(UserFactory)
    title  = Faker("sentence")
```

```python
# In-memory — no DB required
user = UserFactory.build(admin=True)

# Persisted
user  = await UserFactory.create(session)
posts = await PostFactory.create_batch(session, 5)

# Fast bulk insert — no hooks fired, no SubFactory resolution
rows  = await UserFactory.create_batch(session, 10_000, bulk=True)
```

`AutoFactory[T]` generates sensible defaults from mapper introspection, with
name-based smart defaults (`email` → `faker.email()`, `phone` → `faker.phone_number()`, etc.):

```python
class UserFactory(AutoFactory[User]):
    model = User
```

---

## Helpers

```python
from seedling import upsert, truncate_tables, reset_sequences, deferred_constraints

await upsert(session, User, {"id": 1, "email": "a@b.com"})   # idempotent insert
await truncate_tables(session, User, Post, cascade=True)      # dialect-aware TRUNCATE
await reset_sequences(session, User)                          # PostgreSQL: reset SERIAL

async with deferred_constraints(session):                     # PostgreSQL: defer FKs
    ...
```

---

## State tracking

```bash
seed status                       # show last run per seeder + drift flag
seed run --new-only               # skip seeders whose source hasn't changed
seed run --force                  # force re-run even if --new-only would skip
```

Disable per-project:

```toml
[tool.seedling]
state_tracking = false
```

---

## pytest integration

```python
# conftest.py
@pytest.fixture(scope="session")
def seedling_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    return async_sessionmaker(engine, expire_on_commit=False)
```

```python
from seedling.pytest_plugin import seed

@seed(UserSeeder)
async def test_with_user(seedling_transactional_session):
    # UserSeeder ran before the test body;
    # session is rolled back automatically after the test
    ...
```

---

## CLI reference

| Command | Description |
|---------|-------------|
| `seed run` | Run seeders in dependency order |
| `seed fresh` | Truncate then re-seed |
| `seed list` | Print resolved execution order |
| `seed status` | Latest run per seeder with drift detection |
| `seed validate` | Static checks: cycles, missing deps, empty envs |
| `seed graph` | Dependency graph (Graphviz DOT or Mermaid) |
| `seed export` | Dump seeded rows to JSON or YAML |
| `seed restore` | Load a fixture file back into the database |
| `seed init` | Scaffold `seeders/` and `factories/` |
| `seed make:seeder <Name>` | Generate a seeder stub |
| `seed make:factory <module:ClassName>` | Generate a factory stub |

See the [CLI reference](https://arthurvasconcelos.github.io/seedling/cli/) for full options and flags.

---

## Stability

From `1.0.0` onward, seedling follows [Semantic Versioning](https://semver.org/): breaking changes only on major version bumps.

---

## Documentation

Full docs: [https://arthurvasconcelos.github.io/seedling](https://arthurvasconcelos.github.io/seedling)

---

## License

MIT — see [LICENSE](LICENSE).

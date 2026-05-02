# Cookbook

Recipes for common patterns that go beyond the basics.

---

## Cyclic foreign keys

Some schemas have mutually referencing tables — for example, a `Company` that has a
`ceo_id` FK to `Person`, and a `Person` that has an `employer_id` FK to `Company`.
Standard insertion order cannot satisfy both constraints simultaneously.

**Solution: defer FK constraints (PostgreSQL), then break the cycle with a two-step insert.**

```python
from seedling import Seeder, deferred_constraints, DEV_AND_TEST
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from myapp.models import Company, Person

class OrgChartSeeder(Seeder):
    environments = DEV_AND_TEST
    models = [Company, Person]

    async def run(self, session: AsyncSession) -> None:
        async with deferred_constraints(session):
            # 1. Insert companies with no CEO yet
            acme = Company(name="Acme Corp", ceo_id=None)
            session.add(acme)
            await session.flush()

            # 2. Insert persons referencing the company
            alice = Person(name="Alice", employer_id=acme.id)
            session.add(alice)
            await session.flush()

            # 3. Update the company's CEO now that Alice has an id
            acme.ceo_id = alice.id
            await session.commit()
```

`deferred_constraints()` is a no-op on SQLite and MySQL/MariaDB — for those dialects,
break the cycle by inserting with `NULL` and updating in a second statement (same
pattern, no context manager needed).

---

## Polymorphic models

### Single-table inheritance (STI)

SQLAlchemy STI uses a `type` discriminator column to select the concrete class.
Create one factory per concrete subclass:

```python
from sqlalchemy.orm import DeclarativeBase, mapped_column
from sqlalchemy import String
from seedling import Factory, Faker

class Base(DeclarativeBase):
    pass

class Employee(Base):
    __tablename__ = "employee"
    id: int = mapped_column(primary_key=True)
    name: str = mapped_column(String)
    type: str = mapped_column(String)
    __mapper_args__ = {"polymorphic_on": "type", "polymorphic_identity": "employee"}

class Manager(Employee):
    reports_count: int = mapped_column(default=0)
    __mapper_args__ = {"polymorphic_identity": "manager"}

class Engineer(Employee):
    stack: str = mapped_column(String, nullable=True)
    __mapper_args__ = {"polymorphic_identity": "engineer"}


class ManagerFactory(Factory[Manager]):
    model = Manager
    name  = Faker("name")

class EngineerFactory(Factory[Engineer]):
    model   = Engineer
    name    = Faker("name")
    stack   = "Python"
```

Each factory targets the concrete subclass. SQLAlchemy fills in `type` automatically
from `__mapper_args__["polymorphic_identity"]`.

### Joined-table inheritance (JTI)

JTI works the same way — declare a factory for each concrete subclass. The base-table
columns are inherited through the normal SQLAlchemy mapper chain and you don't need to
do anything special in the factory.

---

## JSONB and arrays (PostgreSQL)

PostgreSQL JSONB and ARRAY columns are not covered by `AutoFactory` smart defaults.
Declare them explicitly:

```python
from seedling import Factory, Faker, LazyAttribute
from myapp.models import Article

class ArticleFactory(Factory[Article]):
    model    = Article
    title    = Faker("sentence", nb_words=6)

    # JSONB column
    metadata = LazyAttribute(lambda f: {
        "tags":    ["python", "async"],
        "source":  "import",
        "version": 1,
    })

    # ARRAY column
    keywords = LazyAttribute(lambda f: [
        Faker("word").generate({}),
        Faker("word").generate({}),
    ])
```

For randomised JSONB content, use `faker` inside `LazyAttribute`:

```python
from seedling import faker

metadata = LazyAttribute(lambda f: {
    "score":   faker.random_int(0, 100),
    "tags":    faker.words(3),
    "created": faker.iso8601(),
})
```

---

## Time-series data

Seed rows with monotonically increasing or decreasing timestamps using `Sequence`
and the `datetime` module:

```python
from datetime import UTC, datetime, timedelta
from seedling import Factory, Sequence
from myapp.models import Event

_BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)

class EventFactory(Factory[Event]):
    model      = Event
    name       = Sequence(lambda n: f"event-{n:04d}")
    # Each event is 1 hour after the previous one
    occurred_at = Sequence(lambda n: _BASE_TIME + timedelta(hours=n))
```

For the last N days of data, compute from the current time:

```python
from datetime import UTC, datetime, timedelta
from seedling import Factory, Sequence

class MetricFactory(Factory[Metric]):
    model      = Metric
    value      = Sequence(lambda n: float(n % 100))
    recorded_at = Sequence(
        lambda n: datetime.now(UTC) - timedelta(days=30) + timedelta(hours=n)
    )
```

To seed a full 30-day window in a seeder:

```python
class MetricsSeeder(Seeder):
    environments = DEV_AND_TEST
    models = [Metric]

    async def run(self, session: AsyncSession) -> None:
        await MetricFactory.create_batch(session, 30 * 24)  # one per hour
```

---

## Large tables

### Use `bulk=True` for 10 000+ rows

`create_batch(session, n, bulk=True)` uses a single `INSERT ... RETURNING` statement
instead of N per-row round trips. It is significantly faster for large batches.

```python
await UserFactory.create_batch(session, 100_000, bulk=True)
```

**Limitations:** `@post_generation` hooks and `RelatedFactory` / `RelatedFactoryList`
do not fire. `SubFactory` and FK auto-resolve fields are omitted — pass them as
explicit overrides:

```python
await PostFactory.create_batch(session, 50_000, bulk=True, author_id=fixed_user_id)
```

### Disable state tracking for pure performance runs

State tracking opens extra sessions per seeder to write state rows. Disable it when
you only care about speed:

```python
runner = SeederRunner(session_factory, env="staging", state_tracking=False)
```

Or per-project:

```toml
[tool.seedling]
state_tracking = false
```

### Chunked seeding for very large datasets

If you need to seed tens of millions of rows, chunk the work to avoid memory pressure:

```python
class BigTableSeeder(Seeder):
    environments = DEV_AND_TEST
    models = [Event]

    CHUNK_SIZE = 10_000
    TOTAL      = 1_000_000

    async def run(self, session: AsyncSession) -> None:
        for _ in range(self.TOTAL // self.CHUNK_SIZE):
            await EventFactory.create_batch(session, self.CHUNK_SIZE, bulk=True)
```

Each `create_batch` call issues one INSERT statement; the loop keeps peak memory
proportional to `CHUNK_SIZE`, not `TOTAL`.

### Parallel seeders for independent tables

If you have multiple large tables with no FK relationship, register their seeders
without `depends_on` — the runner will execute them in parallel:

```python
class UserSeeder(Seeder):
    environments = DEV_AND_TEST
    models = [User]
    async def run(self, session):
        await UserFactory.create_batch(session, 100_000, bulk=True)

class ProductSeeder(Seeder):
    environments = DEV_AND_TEST
    models = [Product]
    async def run(self, session):
        await ProductFactory.create_batch(session, 500_000, bulk=True)

# No depends_on — these run in parallel
runner.register(UserSeeder, ProductSeeder)
```

---

## Alembic post-upgrade hook

Run seeders automatically after Alembic migrations by hooking into `env.py`:

```python
# alembic/env.py
from alembic import context

def run_migrations_online() -> None:
    # ... standard async alembic setup ...
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    # After migrations complete, run seeders in the test environment
    if context.get_x_argument(as_dictionary=True).get("seed"):
        import asyncio
        from myapp.seeders import create_runner
        asyncio.run(create_runner("test").run())
```

Trigger it via:

```bash
alembic -x seed=true upgrade head
```

---

## Transactional test fixtures

Use `seedling_transactional_session` to get a session that auto-rolls back after each
test, keeping the database clean without truncation:

```python
# conftest.py
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

@pytest.fixture(scope="session")
def seedling_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    return async_sessionmaker(engine, expire_on_commit=False)


# test_orders.py
from seedling.pytest_plugin import seed

@seed(UserSeeder, OrderSeeder)
async def test_order_total(seedling_transactional_session):
    session = seedling_transactional_session
    # Both seeders ran before this test body.
    # Any changes made in this test are rolled back automatically.
    orders = await session.execute(select(Order))
    ...
```

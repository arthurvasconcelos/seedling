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
      link: /getting-started
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

## How it compares

For an async SQLAlchemy 2.0 app that needs both **fixture factories** and a
**seeder pipeline**, the alternatives are usually factory_boy plus a
hand-rolled script. Here's the same job, three ways.

### Seed 1 000 rows + run a dependent seeder

::: code-group

```python [Seedling]
class UserFactory(AutoFactory[User]):
    model = User


class UserSeeder(Seeder):
    environments = DEV_AND_TEST

    async def run(self, session):
        await UserFactory.create_batch(session, 1000, bulk=True)


class ProfileSeeder(Seeder):
    depends_on = [UserSeeder]
    environments = DEV_AND_TEST

    async def run(self, session): ...


runner = SeederRunner(session_factory, env="development")
runner.register(UserSeeder, ProfileSeeder)
await runner.run()
```

```python [factory_boy + hand-rolled]
class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = "flush"

    name = factory.Faker("name")
    email = factory.Faker("email")
    # ...every column declared manually


# factory_boy is sync — bridge to async yourself
def seed_users(sync_session):
    UserFactory._meta.sqlalchemy_session = sync_session
    UserFactory.create_batch(1000)


def seed_profiles(sync_session): ...


# Ordering, environments, idempotency, parallel — DIY
seed_users(session)
seed_profiles(session)
```

:::

### Feature matrix

| | Seedling | factory_boy | raw SQLAlchemy |
|---|:---:|:---:|:---:|
| Async-native API | ✅ | ❌ (sync only) | ✅ |
| Zero-config field defaults from mapper | ✅ `AutoFactory` | ❌ declare each | ❌ |
| Bulk `INSERT … RETURNING` path | ✅ `bulk=True` | ❌ | ✅ manual |
| Seeder orchestration (`depends_on`) | ✅ | ❌ | ❌ |
| Environment gating (dev / test / prod) | ✅ | ❌ | ❌ |
| State tracking + drift detection | ✅ | ❌ | ❌ |
| Parallel level execution | ✅ | ❌ | ❌ |
| pytest fixtures + `@seed()` decorator | ✅ | ❌ | ❌ |
| CLI (`seed run`, `fresh`, `graph`, …) | ✅ | ❌ | ❌ |
| Per-row throughput (1 000 rows, SQLite) | 7 900 rows/s | **16 700 rows/s** | 8 200 rows/s |
| Bulk throughput (1 000 rows, SQLite) | **90 000 rows/s** | — | 520 000 rows/s |

Honest trade-off: factory_boy is still **~2× faster per-row** because its
sync code path has no event-loop overhead. Seedling's per-row path now matches
raw `session.add()` + flush, and `bulk=True` is ~5× faster than factory_boy.
See the [benchmarks](/benchmarks) page for full numbers.

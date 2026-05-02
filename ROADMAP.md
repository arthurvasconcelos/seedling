# Roadmap

sqlalchemy-seedling shipped its 1.0 release candidate in May 2026. Below is the
history of phases and what each one delivered.

## 0.2 — Foundations & Polish *(shipped)*

Infrastructure work that everything else builds on:
structured logging via structlog with a per-run UUID, stricter typing, a
tighter production guard, dialect helpers (`truncate_tables`,
`reset_sequences`, deferred FK constraints), MySQL/MariaDB upsert support,
`seed list` output flags, and a MariaDB entry in the CI matrix.

## 0.3 — State Tracking & Audit *(shipped)*

Adds a `seedling_state` table (auto-created on first run, similar to
Alembic's `alembic_version`). The runner records every execution — start
time, finish time, status, error, rows seeded, and a content hash of the
seeder's `run` method for drift detection. New commands: `seed status`,
`seed validate`, and `seed graph`. New flags: `--new-only` (skip seeders
whose hash matches latest success) and `--force`.

## 0.4 — Factory Power *(shipped)*

Factory parity with — and beyond — factory_boy:
`AutoFactory[Model]` with mapper introspection and smart defaults,
a factory registry, declarative `Trait` classes (replaces `as_trait()`,
breaking change), `@post_generation` hooks, `RelatedFactory`,
`SelfAttribute`, `Iterator`, `Faker(...)` descriptor, `build_dict()`,
bulk insert path, and deterministic seeding via `Factory.seed(n)`.

## 0.5 — Scaffolding & Fixtures *(shipped)*

`seed init`, `seed make:seeder`, `seed make:factory` (uses AutoFactory
introspection), `seed restore` (inverse of `seed export`), optional YAML
support, tag-based filtering, and a `seedling_transactional_session` pytest
fixture that wraps each test in a SAVEPOINT and rolls back.

## 1.0 RC — Stabilization & Docs *(current)*

API freeze, migration guide from factory_boy, a cookbook covering common
patterns (cyclic FKs, JSONB, polymorphic models, large tables), example apps
(FastAPI + Alembic, Litestar, plain script), performance benchmarks, and
mkdocs polish. A release-candidate period invites feedback before the SemVer
commitment locks in.

---

Items explicitly out of scope for 1.0 (community PRs welcome after 1.0):
sync runner, MSSQL/Oracle upsert dialects, OpenTelemetry tracing, Hypothesis
strategies, CSV bulk loader.

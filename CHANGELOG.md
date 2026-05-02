# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0rc1] - 2026-05-02

### Added

- **`__version__`** — `seedling.__version__` is now a public string constant.
- **`docs/migration.md`** — side-by-side migration guide from `factory_boy` covering
  all common patterns: `LazyAttribute`, `Sequence`, `SubFactory`, `Trait`, `@post_generation`,
  `RelatedFactory`, bulk insert, `Faker`, and `AutoFactory`.
- **`docs/cookbook.md`** — recipes for cyclic foreign keys, polymorphic models, JSONB /
  array columns, time-series data, large tables (`bulk=True`, chunked seeding), and
  transactional test fixtures.
- **Example apps** — three fully-wired example applications:
  - `examples/script/` — plain SQLAlchemy script, no framework. Runs end-to-end
    against SQLite with `AutoFactory` factories.
  - `examples/fastapi_alembic/` — FastAPI app with Alembic migrations, async seeder
    runner, and `AutoFactory` factories targeting PostgreSQL.
  - `examples/litestar/` — Litestar app with the same seeder/factory structure.
- **`tests/test_smoke_examples.py`** — CI smoke tests: `examples/script/` runs a full
  seed + export cycle against in-memory SQLite; FastAPI and Litestar examples are
  verified as import-clean.
- **`benchmarks/bench_create_batch.py`** — benchmark comparing per-row `create_batch()`
  vs `create_batch(bulk=True)`.
- **`benchmarks/bench_parallel.py`** — benchmark comparing parallel level execution vs
  `max_parallel=1` (sequential).
- **`mkdocs.yml`** — search plugin enabled (`search.highlight`, `search.suggest`);
  `state-tracking.md`, `migration.md`, and `cookbook.md` added to the navigation.

### Changed

- **`seedling/__init__.py`** — `compute_hash`, `ensure_state_table`, and
  `get_latest_states` removed from `__all__` and the public import surface. They
  remain accessible via `seedling.state` for internal use but are not part of the
  stable public API.
- **`pyproject.toml`** — version bumped to `1.0.0rc1`.
- **`ROADMAP.md`** — all phases (0.2 through 0.5) marked as shipped; 1.0 RC marked
  as current.
- **`README.md`** — full rewrite reflecting the complete feature set: state tracking,
  all CLI commands, `AutoFactory`, `Trait`, `@post_generation`, helpers, pytest
  integration, and SemVer commitment.
- **`docs/`** — all existing pages updated to cover features added in 0.2–0.5:
  - `index.md`: complete feature table, updated quickstart.
  - `seeders.md`: `tags` class variable, `before_run`/`after_run`/`on_error` hooks.
  - `runner.md`: constructor parameters, `run()` / `fresh()` / `list_seeders()` tag
    and state-tracking kwargs, transactional mode, lifecycle hooks.
  - `cli.md`: all commands and flags, including `status`, `validate`, `graph`,
    `restore`, `init`, `make:seeder`, `make:factory`, `--new-only`, `--force`,
    `--max-parallel`, `--tag`, `--quiet`, `--verbose`, and updated production guard.
  - `configuration.md`: `state_tracking` option documented.

---

## What's new since 0.1

sqlalchemy-seedling started as a thin async wrapper around the core SQLAlchemy
seeding pattern and has grown into a full seeder + factory platform.

**0.2 — Foundations:** structured logging via `structlog` with a per-run UUID,
dialect helpers (`truncate_tables`, `reset_sequences`, `deferred_constraints`),
MySQL/MariaDB upsert, `seed list` output flags, a CI matrix with PostgreSQL and
MariaDB, and the Rich CLI visual overhaul.

**0.3 — State tracking:** a `seedling_state` table (auto-created, append-only,
similar to Alembic's `alembic_version`) that records every seeder execution with
start/finish timestamps, status, error, and a SHA-256 content hash of the seeder's
`run()` source. New commands: `seed status`, `seed validate`, `seed graph`. New flags:
`--new-only`, `--force`, `--max-parallel`. Seeder and runner lifecycle hooks. Transactional
mode (`SeederRunner(transactional=True)`) for test isolation.

**0.4 — Factory power:** `AutoFactory[T]` with mapper introspection and name-based
smart defaults; factory registry; declarative `Trait` classes (replacing `as_trait()`);
async-first `@post_generation` hooks; `RelatedFactory` / `RelatedFactoryList`;
`SelfAttribute`, `Iterator`, `Faker`, `Skip` descriptors; `build_dict()`, bulk insert
path (`bulk=True`), `reset_sequence()`, and `seed()` for deterministic faker output.

**0.5 — Scaffolding and fixtures:** `seed init`, `seed make:seeder`, `seed make:factory`
(uses AutoFactory introspection), `seed restore`, optional YAML support, tag-based
filtering (`tags` on `Seeder`, `--tag` on CLI), and the `seedling_transactional_session`
pytest fixture.

**1.0 RC:** API freeze, docs rewrite, migration guide from factory_boy, cookbook,
example apps, benchmarks, and the SemVer stability commitment.

---

## [0.5.0] - 2026-05-02

### Added

- **`seed restore <file>`** — inverse of `seed export`. Inserts rows from a
  fixture file into the database. Tables are matched to registered seeder
  models by `__tablename__`; unknown tables are skipped with a warning.
- **YAML support (`[yaml]` extra)** — `pip install sqlalchemy-seedling[yaml]`
  adds PyYAML. Both `seed export` and `seed restore` auto-detect format from
  the output file extension (`.json` / `.yaml` / `.yml`). PyYAML is never a
  hard dependency.
- **Internal `_formats` module** — pluggable load/dump abstraction used by
  `export` and `restore`; handles `datetime`, `date`, `Decimal`, and `UUID`
  serialisation for JSON.
- **`Seeder.tags`** — new `ClassVar[set[str]]` on `Seeder` (default `set()`).
  Tag seeders with arbitrary labels (e.g. `tags = {"demo", "smoke"}`).
- **`seed run --tag <label>`** — filter the run to seeders whose `tags` set
  intersects the given label(s). Repeatable: `--tag demo --tag smoke`. Same
  flag added to `seed fresh` and `seed list`.
- **`runner.run(tags=…)` / `runner.fresh(tags=…)` / `runner.list_seeders(tags=…)`**
  — tag filtering in the programmatic API.
- **`@seed(UserSeeder)` pytest helper** — importable from
  `seedling.pytest_plugin`. Avoids a pytest 9.x ambiguity where
  `@pytest.mark.seed(SomeClass)` is applied to the class rather than the
  test. `@pytest.mark.seed([UserSeeder])` (list form) also works.
- **`_seedling_seed_marker` autouse fixture** — runs the seeders listed in a
  `@seed(…)` mark before the test body, via the `seedling_runner` fixture.
- **`seedling_transactional_session` fixture** — wraps each test in a
  SQLAlchemy `SAVEPOINT` (`begin_nested`) that is automatically rolled back
  after the test. Keeps the database clean without truncation.
- **`_seedling_runner_for_marker` internal fixture** — declared as an explicit
  dependency of `_seedling_seed_marker` to avoid `Runner.run() cannot be
  called from a running event loop` errors in pytest-asyncio when fixture
  chains are resolved lazily.
- **`seed init`** — scaffolds `seeders/` and `factories/` packages and appends
  a `[tool.seedling]` block to `pyproject.toml`. Opinionated layout, no
  `--minimal` flag.
- **`seed make:seeder <Name>`** — generates a seeder stub in
  `seeders/<name_snake>.py`.
- **`seed make:factory <module:ClassName>`** — generates an `AutoFactory`
  stub for a SQLAlchemy model in `factories/<name_snake>.py`. Introspects
  non-nullable string columns to suggest explicit field stubs.
- **`resolver.resolve_with_deps` now handles unregistered seeders** — seeders
  explicitly passed to `runner.run()` but not in the registry are now
  resolved correctly (sorted by their own dependency graph and appended after
  registry order). Previously they were silently dropped.
- **`seedling_session_factory` returns `None` by default** — the plugin
  fixture no longer raises `NotImplementedError` on import; it raises only
  when `seedling_runner` is used explicitly without being configured. This
  prevents the autouse `_seedling_seed_marker` fixture from breaking projects
  that have not configured the session factory.

### Changed

- `seed export` now delegates to the `_formats` module and supports `.yaml` /
  `.yml` output paths in addition to `.json`.

## [0.4.0] - 2026-05-02

### Added

- **`Factory.seed(n)`** — classmethod that seeds the shared `faker` instance and any
  locale-specific `Faker(...)` descriptor instances declared on the factory's MRO for
  deterministic output. Call once per test to make faker-generated values reproducible.
- **`create_batch(..., bulk=True)`** — new keyword argument on `Factory.create_batch()` that
  uses a single `INSERT ... RETURNING` statement (SQLAlchemy Core ORM DML) instead of N
  per-row `create()` calls. Significantly faster for large batches. Limitations: `@post_generation`
  hooks and `RelatedFactory`/`RelatedFactoryList` descriptors do **not** fire; `SubFactory`
  and auto-resolved FK fields are omitted from the insert dict (supply them as overrides).
- **`Factory.build_dict(**overrides)`** — same contract as `build()` but returns a plain
  `dict` instead of an ORM instance. Accepts overrides, trait kwargs, and all descriptors.
  SubFactory fields are omitted (same as `build()`). Useful for fixtures, assertions, and
  feeding data to non-ORM code.
- **`Factory.reset_sequence(value=0)`** — classmethod that resets the `Sequence` counter for
  the factory to *value* (next build uses *value* as the first sequence number) and also resets
  all `Iterator` descriptors anywhere in the factory's MRO back to their first element. Typical
  use: call once per test to get predictable sequence values.
- **`SelfAttribute(attr_path, default=None)`** — reference a sibling field by name in the
  same factory call. Dot-notation traverses attributes of the resolved value. Returns
  `default` when the referenced field is not yet available.
- **`Iterator(values)`** — cycle through a fixed list of values, advancing by one per
  instance built. Call `iterator.reset()` to restart the cycle.
- **`Faker(provider, *args, locale=None, **kwargs)`** — call a `faker` provider by name each
  time an instance is built. Optional `locale` creates a locale-specific faker instance.
  Replaces the pattern of wrapping `faker.xxx()` in a `LazyAttribute`.
- **`Skip`** — singleton sentinel that tells a factory to omit a field entirely. Useful in
  `AutoFactory` subclasses to suppress a smart default; the caller must then supply the value
  via an explicit override kwarg.
- **Factory registry** — every `Factory[T]` subclass that declares `model = ...` on its own body now self-registers in a global registry. `get_factory(ModelClass)` returns the registered factory, or `None`. Used internally by `AutoFactory` for FK resolution; also available as a public API for advanced use.
- **`AutoFactory[Model]`** — subclass instead of `Factory[T]` to get automatic field defaults
  from SQLAlchemy mapper introspection. Primary keys are skipped; FK columns resolve via the
  registry (non-nullable FK with no registered factory raises `AutoFactoryResolutionError` at
  `create()` time; nullable FK with no registered factory is left unset). Explicitly declared
  fields always override auto-generated ones.
  - `class Meta: smart_defaults = True` (default-on) — name-based heuristics: `email` →
    `faker.email()`, `first_name` → `faker.first_name()`, `phone` → `faker.phone_number()`, etc.
    Set `smart_defaults = False` to disable.
- **`AutoFactoryResolutionError`** — new exception raised when `AutoFactory` cannot resolve a
  non-nullable FK column at `create()` time.
- **`class Trait` declarative syntax** — define traits as inner classes of a factory that
  subclass `Trait`. Apply via bool kwargs; multiple traits stack left-to-right, later wins on
  conflict; explicit kwargs always beat trait fields; `trait_name=False` suppresses the trait
  without forwarding the kwarg to the model. `LazyAttribute` and other descriptors work inside
  `Trait` bodies. Traits inherit through the factory MRO.

- **`RelatedFactory(factory, **kwargs)`** — declare as a factory attribute to create one
  related instance after the main instance is persisted (after `@post_generation` hooks).
  Callable kwargs receive the parent instance; non-callable kwargs are forwarded as-is.
  Silently skipped in `build()`. Inherits through the factory MRO.
- **`RelatedFactoryList(factory, size=1, **kwargs)`** — like `RelatedFactory` but creates
  *size* related instances. `size=0` is valid and creates nothing.
- **`@post_generation`** — async-first decorator for post-create hooks. The decorated
  function receives `(instance, session)` after the instance has been flushed and refreshed.
  Hooks are silently skipped in `build()`. Multiple hooks on one factory fire in MRO order
  (base → subclass, declaration order within a class). Child factories inherit parent hooks;
  a child can override a parent hook by re-declaring a hook with the same name. Sync functions
  are also accepted and called without `await`.

### Documentation

- `docs/factories.md` — full rewrite covering all Phase 0.4 descriptors, `AutoFactory`,
  `Trait`, `@post_generation`, `RelatedFactory`/`RelatedFactoryList`, `build_dict()`,
  bulk insert, `reset_sequence()`, `seed()`, and the factory registry.
- Migration guide from `as_trait()` to the declarative `Trait` syntax included in
  `docs/factories.md`.

### Removed

- **`Factory.as_trait()`** *(breaking)* — replaced by the declarative `class Trait` syntax.
  Migration: move `as_trait(field=val)` call-site logic into an inner `Trait` subclass and
  apply it via `MyFactory.build(trait_name=True)` / `await MyFactory.create(session, trait_name=True)`.

## [0.3.0] - 2026-05-02

### Added

**State tracking**
- `seedling_state` table — auto-created via `CREATE TABLE IF NOT EXISTS` on first run
  (no migrations needed, similar to Alembic's `alembic_version`). Columns: `id`,
  `seeder_name`, `env`, `run_id`, `status`, `started_at`, `finished_at`,
  `duration_ms`, `error`, `rows_seeded`, `content_hash`. Append-only history —
  one row per execution.
- Content hash — SHA-256 of each seeder's `run()` source, stored on every execution.
  Drift is flagged when the current hash differs from the stored hash.
- `[tool.seedling] state_tracking = true` — default-on; opt out per-project via
  `state_tracking = false` in `pyproject.toml`, or per-runner via
  `SeederRunner(..., state_tracking=False)`.

**Seeder hooks**
- `Seeder.before_run(session)` — async hook called before `run()`. Override to add
  pre-seeding logic.
- `Seeder.after_run(session)` — async hook called after a successful `run()`.
- `Seeder.on_error(session, exc)` — async hook called on failure. Default no-op.

**Runner lifecycle hooks**
- `SeederRunner.before_run(run_id, env)` — override to react before the run starts.
- `SeederRunner.after_run(run_id, env)` — override to react after a successful run.
- `SeederRunner.on_run_error(run_id, env, exc)` — override to react on run failure.

**New `SeederRunner` constructor parameters**
- `state_tracking: bool = True` — enable/disable state tracking.
- `transactional: bool = False` — wrap the entire run in a single transaction;
  rolls back everything if any seeder raises. State tracking is skipped in
  transactional mode.
- `max_parallel: int | None = None` — cap concurrency within a dependency level.

**New `run()` flags**
- `new_only: bool = False` — skip seeders whose latest state is `success` and whose
  content hash matches.
- `force: bool = False` — override `new_only` and always re-run.

**New CLI commands**
- `seed status [--env ENV] [--json]` — show latest run per seeder with drift flag.
- `seed validate [--env ENV]` — static checks: cycles, missing deps, empty
  environments, missing models. Exits 1 if any issues found.
- `seed graph [SEEDERS...] [--env ENV] [--mermaid]` — Graphviz DOT (default) or
  Mermaid flowchart of the dependency graph.

**New CLI flags**
- `seed run --new-only` — skip up-to-date seeders.
- `seed run --force` — override `--new-only`.
- `seed run --max-parallel N` — cap concurrency within a level.
- `seed fresh --max-parallel N` — same for fresh runs.

**Documentation**
- `docs/state-tracking.md` — schema reference, drift semantics, `fresh` semantics,
  opt-out instructions, and all new flags.

### Changed
- `seed fresh` now wipes `seedling_state` rows for affected seeders before
  truncating and re-seeding (clean-slate semantics).

## [0.2.0] - 2026-05-02

### Added

**Logging**
- `structlog` dependency (>=24.0). The runner now emits structured log events:
  `run.start`, `seeder.start`, `seeder.finish`, `run.finish`, `fresh.start`, `fresh.finish`.
  All events carry a `run_id` UUID (unique per `run()` / `fresh()` call) and the current `env`.

**Helpers**
- `truncate_tables(session, *models, cascade=True)` — dialect-aware table truncation:
  `TRUNCATE … CASCADE` on PostgreSQL, `SET FOREIGN_KEY_CHECKS=0` + `TRUNCATE` on
  MySQL/MariaDB, `DELETE FROM` on SQLite.
- `reset_sequences(session, *models)` — resets PostgreSQL SERIAL/IDENTITY sequences
  to 1 after truncation. No-op on SQLite and MySQL/MariaDB.
- `deferred_constraints(session)` — async context manager that defers all
  constraints for the duration of the block on PostgreSQL. No-op on other dialects.
- MySQL/MariaDB upsert — `upsert()` now uses `INSERT IGNORE` on MySQL and MariaDB
  (in addition to the existing PostgreSQL `ON CONFLICT DO NOTHING` and SQLite
  `INSERT OR IGNORE` branches).

**CLI**
- `seed list --quiet` / `-q` — prints seeder names only, one per line.
- `seed list --verbose` / `-v` — shows both `depends_on` and `environments` for each seeder.
- `seed list --json` — outputs the execution order as a JSON array
  (`name`, `depends_on`, `environments` keys).

**Production guard**
- `seed run --env production` and `seed fresh --env production` now require the
  `SEEDLING_ALLOW_PROD=1` environment variable in addition to the interactive
  confirmation prompt.

**Documentation**
- `ROADMAP.md` — public high-level roadmap (phases 0.2 → 1.0 RC).
- `RELEASING.md` — step-by-step release checklist, including the 1.0 RC process.
- README "On the horizon" section — teaser for upcoming phases.

**Examples**
- `examples/_dev_smoke/` — minimal FastAPI app exercising `SeederRunner`, factories,
  `upsert`, and `truncate` against a SQLite database.

**CI**
- PostgreSQL 16 and MariaDB 11 service containers added to the CI matrix.
  Dialect-specific tests are skipped locally unless `SEEDLING_TEST_PG_URL` and
  `SEEDLING_TEST_MARIADB_URL` are set.

### Changed

- All `print()` calls in `runner.py` replaced with structlog events.
- All `print()` calls in `cli.py` replaced with `typer.echo()` (idiomatic typer output).
- `Factory[T]`: removed `# type: ignore[no-any-return]` — now uses `cast(T, ...)` for
  clean mypy output without suppression comments.
- `_get_runner` in `cli.py`: removed `# type: ignore[no-any-return]` — now annotates
  the callable as `Callable[[str], SeederRunner]`.
- **CLI visual overhaul** (using `rich`, already a transitive dep of `typer`):
  - `seed run` / `seed fresh` show a transient spinner progress bar while executing,
    with a seeder counter and elapsed time. Completes with a styled green `✓ Done` line.
  - `seed list` now renders a Rich table (name, environments, depends-on columns).
    `--verbose` adds an Idempotent column. `--quiet` and `--json` remain plain-text.
  - Error messages are styled (`✗` in red to stderr).
  - The production guard shows an amber `⚠ Production` panel before the confirm prompt.
  - `seed export` completion line is styled.
- `rich>=13` added as an explicit project dependency (was already a transitive dep via `typer`).

### Added (tools)

- `justfile` with `install`, `fmt`, `lint`, `test`, `check`, `smoke`, and `docs` tasks.

## [0.1.0] - 2026-03-31

### Added

**Core**
- `Seeder` base class with `depends_on`, `environments`, `idempotent`, and `models` class variables.
- `SeederRunner` with `register`, `discover`, `run`, `fresh`, `list_seeders`, `get_by_name`, and `export`.
- Kahn's topological sort (`topological_sort`, `topological_levels`, `resolve_with_deps`) with `CircularDependencyError` and `MissingDependencyError`.
- Parallel execution — seeders within the same dependency level run concurrently via `asyncio.gather`.
- Auto-discovery via `SeederRunner.discover(package)` — imports all modules under a package and registers every `Seeder` subclass found.

**Factory**
- `Factory[T]` with `LazyAttribute`, `Sequence`, `SubFactory`, and `as_trait()`.
- `build()`, `build_batch()`, `create()`, `create_batch()` class methods.

**Helpers**
- Dialect-aware `upsert()` helper (PostgreSQL `ON CONFLICT DO NOTHING` / SQLite `INSERT OR IGNORE`).

**CLI**
- `seed run` — runs seeders in dependency order; prompts for confirmation when `--env production`.
- `seed fresh` — truncates affected tables then re-seeds; prompts for confirmation when `--env production`.
- `seed list` — prints resolved execution order without running anything.
- `seed export` — queries all rows for models declared on registered seeders and writes them to a JSON file (UUID, datetime, and Decimal serialised automatically).
- Configured via `[tool.seedling] runner = "module:func"` in the consumer's `pyproject.toml`.

**pytest plugin**
- `seedling_runner` fixture via `pytest11` entry point.
- Override `seedling_session_factory` and `seedling_env` fixtures to configure the runner in tests.

**Environment constants**
- `DEV`, `TEST`, `PROD`, `ALL`, `DEV_AND_TEST`.

**Packaging**
- PEP 561 `py.typed` marker.
- MIT licence.

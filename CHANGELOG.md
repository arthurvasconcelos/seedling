# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

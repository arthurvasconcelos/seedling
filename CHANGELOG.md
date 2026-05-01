# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

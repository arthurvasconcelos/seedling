# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

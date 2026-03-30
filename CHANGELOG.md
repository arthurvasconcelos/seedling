# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `topological_levels()` resolver — groups seeders by dependency level so independent branches can be executed concurrently.
- Parallel execution in `SeederRunner.run()` and `SeederRunner.fresh()` — seeders within the same dependency level now run concurrently via `asyncio.gather`.

## [0.1.0] - 2026-03-30

### Added
- `Seeder` base class with `depends_on`, `environments`, and `idempotent` class variables.
- `SeederRunner` with `register`, `run`, `fresh`, `list_seeders`, and `get_by_name`.
- Kahn's topological sort (`topological_sort`, `resolve_with_deps`) with `CircularDependencyError` and `MissingDependencyError`.
- `Factory[T]` with `LazyAttribute`, `Sequence`, `SubFactory`, and `as_trait()`.
- Dialect-aware `upsert()` helper (PostgreSQL `ON CONFLICT DO NOTHING` / SQLite `INSERT OR IGNORE`).
- Environment constants: `DEV`, `TEST`, `PROD`, `ALL`, `DEV_AND_TEST`.
- Generic Typer CLI (`seed run`, `seed fresh`, `seed list`) configured via `[tool.seedling]` in `pyproject.toml`.
- PEP 561 `py.typed` marker.

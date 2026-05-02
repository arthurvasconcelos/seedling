# State Tracking

Seedling records every seeder execution in a `seedling_state` table that lives in the same database as your seeded data. This gives you an audit trail, drift detection, and the ability to skip seeders that are already up-to-date.

## How it works

On the first call to `seed run` or `seed fresh`, Seedling automatically creates the `seedling_state` table (`CREATE TABLE IF NOT EXISTS`). No migration is needed — it works like Alembic's `alembic_version` table.

Every seeder execution appends one row:

| Column | Type | Description |
|---|---|---|
| `id` | integer | Auto-incrementing primary key |
| `seeder_name` | varchar | Class name of the seeder |
| `env` | varchar | The environment passed to the runner |
| `run_id` | varchar(36) | UUID shared across all seeders in a single `run()` call |
| `status` | varchar | `running`, `success`, or `error` |
| `started_at` | datetime | UTC timestamp when the seeder started |
| `finished_at` | datetime | UTC timestamp when the seeder finished (NULL if still running) |
| `duration_ms` | integer | Wall-clock duration in milliseconds |
| `error` | text | Error message if status is `error` |
| `rows_seeded` | integer | Reserved — NULL by default |
| `content_hash` | varchar(64) | SHA-256 of the `run()` method's source code |

The history is **append-only**: rows are never deleted between normal runs. They are only deleted when you call `seed fresh`, which wipes state for the affected seeders before re-seeding.

## Drift detection

The `content_hash` column stores a SHA-256 hash of the seeder's `run()` source code at the time it was last executed. When `seed status` is shown, the current hash is compared to the stored hash. A mismatch means the seeder's code has changed since it last ran — that run is considered "drifted".

Drift is displayed in `seed status` and is also used by `--new-only` to decide whether a seeder needs to re-run.

## Commands

### `seed status`

Show the latest run per seeder with drift detection:

```
seed status --env development
```

Output:

```
Seeder status  development

 Seeder         Status    Last run              Duration  Drift
 ─────────────────────────────────────────────────────────────
 UserSeeder     success   2026-05-02 12:00:00   42ms      —
 PostSeeder     success   2026-05-02 12:00:01   18ms      ⚠ drift
```

Use `--json` for machine-readable output (useful in CI scripts):

```
seed status --env development --json
```

### `seed validate`

Static checks with no database connection required:

```
seed validate --env development
```

Checks performed:

- **Cycles** — any circular `depends_on` chain raises an error
- **Missing deps** — a seeder that references an unregistered dependency
- **Empty environments** — a seeder whose `environments` set is empty will never run
- **Missing models** — a seeder without a `models` list won't appear in `seed export`

All issues are printed and the command exits with code 1 if any are found.

### `seed graph`

Visualize the dependency graph as Graphviz DOT (default) or Mermaid:

```
# Graphviz DOT — pipe to dot for rendering
seed graph | dot -Tpng -o deps.png

# Mermaid — paste into a .md file or Mermaid Live Editor
seed graph --mermaid
```

## Run flags

### `--new-only`

Skip seeders whose latest state is `success` **and** whose `content_hash` matches the current source. Seeders that have never run, last failed, or have drifted will always run.

```
seed run --new-only
```

This is the opt-in idempotency flag. `seed run` without `--new-only` always runs all seeders and records the result.

### `--force`

Override `--new-only` and run all seeders regardless of state:

```
seed run --new-only --force
```

### `--max-parallel N`

Cap how many seeders run concurrently within a single dependency level:

```
seed run --max-parallel 2
```

Without this flag, all seeders in the same level run in parallel (the 0.2 default).

## Transactional mode

`SeederRunner(transactional=True)` wraps the entire run in a single transaction. All seeders share one session; if any seeder raises, the entire transaction rolls back.

```python
runner = SeederRunner(session_factory, env="test", transactional=True)
```

**Note:** State tracking is skipped in transactional mode. Because the seeder data and state rows would be in the same transaction, a rollback would also roll back the state records, making them unreliable. Use transactional mode for test isolation, not production audit.

## Opting out

Disable state tracking globally for a project via `pyproject.toml`:

```toml
[tool.seedling]
runner = "myapp.seeders:create_runner"
state_tracking = false
```

Or per `SeederRunner` instance:

```python
runner = SeederRunner(session_factory, env="development", state_tracking=False)
```

When disabled, the `seedling_state` table is never created or queried.

## The `fresh` command and state

`seed fresh` wipes state for all affected seeders **before** truncating tables and re-seeding. This gives you a clean slate — history for those seeders in that environment is gone. This is intentional: `fresh` means "start over."

State for seeders in other environments is untouched.

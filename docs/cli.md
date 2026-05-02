# CLI Reference

The `seed` command is installed as an entry point when you install seedling.

All commands read `[tool.seedling]` from the `pyproject.toml` in the current directory.

---

## `seed run [SEEDERS...] [OPTIONS]`

Run seeders in dependency order.

```bash
seed run                              # run all seeders (env: development)
seed run --env test                   # run all test seeders
seed run UserSeeder PostSeeder        # run specific seeders + their deps
seed run --new-only                   # skip seeders whose source hasn't changed
seed run --force                      # re-run all, even if state says success
seed run --max-parallel 4             # cap concurrency to 4 within each level
seed run --tag demo                   # only run seeders tagged "demo"
seed run --tag demo --tag smoke       # union: any seeder matching either tag
seed run --env production             # requires SEEDLING_ALLOW_PROD=1 + confirmation
```

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--env` | `development` | Environment to seed |
| `--new-only` | off | Skip seeders whose latest state is `success` and hash matches |
| `--force` | off | Override `--new-only` — always run all seeders |
| `--max-parallel N` | unlimited | Cap concurrency within a dependency level |
| `--tag LABEL` | — | Filter to seeders with this tag (repeatable) |

---

## `seed fresh [SEEDERS...] [OPTIONS]`

Truncate affected tables then run seeders. Useful for a clean slate.

```bash
seed fresh
seed fresh --env test
seed fresh UserSeeder             # truncate + reseed UserSeeder (and its deps)
seed fresh --tag demo             # truncate + reseed tagged seeders only
seed fresh --env production       # requires SEEDLING_ALLOW_PROD=1 + confirmation
```

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--env` | `development` | Environment to seed |
| `--max-parallel N` | unlimited | Cap concurrency within a dependency level |
| `--tag LABEL` | — | Filter to seeders with this tag (repeatable) |

---

## `seed list [SEEDERS...] [OPTIONS]`

Print the resolved execution order without running anything.

```bash
seed list
seed list --env production
seed list PostSeeder
seed list --tag demo
seed list --quiet                 # names only, one per line
seed list --verbose               # adds Idempotent column
seed list --json                  # machine-readable JSON array
```

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--env` | `development` | Environment to filter by |
| `--tag LABEL` | — | Filter by tag (repeatable) |
| `--quiet` / `-q` | off | Print seeder names only, one per line |
| `--verbose` / `-v` | off | Show idempotent flag in output |
| `--json` | off | Output as JSON array with `name`, `depends_on`, `environments` keys |

---

## `seed status [OPTIONS]`

Show the latest run per seeder with drift detection.

```bash
seed status
seed status --env test
seed status --json
```

Output:

```
Seeder status  development

 Seeder         Status    Last run              Duration  Drift
 ─────────────────────────────────────────────────────────────
 UserSeeder     success   2026-05-02 12:00:00   42ms      —
 PostSeeder     success   2026-05-02 12:00:01   18ms      ⚠ drift
```

A `⚠ drift` flag means the seeder's `run()` source has changed since it last ran. Use `seed run` (without `--new-only`) to re-run it and clear the drift.

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--env` | `development` | Environment to query |
| `--json` | off | Output as JSON array |

---

## `seed validate [OPTIONS]`

Static checks with no database connection required.

```bash
seed validate
seed validate --env production
```

Checks performed:

- **Cycles** — any circular `depends_on` chain
- **Missing deps** — a seeder that references an unregistered dependency
- **Empty environments** — a seeder whose `environments` set is empty will never run
- **Missing models** — a seeder without a `models` list won't appear in `seed export`

All issues are printed and the command exits with code 1 if any are found.

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--env` | `development` | Environment to validate for |

---

## `seed graph [SEEDERS...] [OPTIONS]`

Output the dependency graph as Graphviz DOT (default) or Mermaid.

```bash
# Graphviz DOT — pipe to dot for rendering
seed graph | dot -Tpng -o deps.png

# Mermaid — paste into a .md file or Mermaid Live Editor
seed graph --mermaid

# Only a subset of seeders
seed graph PostSeeder CommentSeeder
```

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--env` | `development` | Environment to graph |
| `--mermaid` | off | Output Mermaid flowchart instead of Graphviz DOT |

---

## `seed export [SEEDERS...] [OPTIONS]`

Query all rows for models declared on registered seeders and write them to a file.

```bash
seed export                           # writes fixtures.json
seed export --output data/seed.json   # custom output path
seed export --output seed.yaml        # YAML output (requires [yaml] extra)
seed export UserSeeder                # export only UserSeeder's models
```

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--env` | `development` | Environment (affects which runner is created) |
| `--output` / `-o` | `fixtures.json` | Output file path (`.json`, `.yaml`, or `.yml`) |

!!! note
    Seeders must declare `models = [MyModel]` for their data to be included.
    UUID, datetime, and Decimal values are serialised to strings automatically.

---

## `seed restore FILE [OPTIONS]`

Load rows from a fixture file back into the database.

```bash
seed restore fixtures.json
seed restore seed.yaml --env test
```

Tables in the fixture that have no matching seeder model are skipped with a warning. Rows are inserted using bulk Core insert — the table order in the fixture must satisfy FK constraints. Fixture files produced by `seed export` are always safe to restore.

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--env` | `development` | Environment (used to resolve the runner) |

---

## `seed init`

Scaffold `seeders/` and `factories/` packages and configure `pyproject.toml`.

```bash
seed init
```

Creates:
- `seeders/__init__.py` — runner factory stub with inline instructions
- `factories/__init__.py` — import index for factory registry
- Appends `[tool.seedling]` to `pyproject.toml`

If either directory already exists, that step is skipped. Run from your project root.

---

## `seed make:seeder NAME`

Generate a seeder stub in `seeders/<name_snake>.py`.

```bash
seed make:seeder UserSeeder
seed make:seeder BlogPostSeeder
```

The name must be CamelCase. A file is created at `seeders/user_seeder.py` (or equivalent snake_case). Requires `seeders/` to exist — run `seed init` first.

---

## `seed make:factory MODULE:CLASSNAME`

Generate a factory stub for a SQLAlchemy model.

```bash
seed make:factory myapp.models:User
seed make:factory myapp.models:BlogPost
```

Introspects the model and generates an `AutoFactory` stub. Non-nullable, non-PK, non-FK string columns are listed as explicit stubs with a `# TODO` comment. Requires `factories/` to exist — run `seed init` first.

---

## Production guard

When `--env production` is passed to `run` or `fresh`, seedling requires both:

1. The `SEEDLING_ALLOW_PROD=1` environment variable must be set.
2. An interactive confirmation prompt must be accepted.

```
⚠  Production
───────────────────────────────────────────
You are about to seed the production environment.
This cannot be undone.
───────────────────────────────────────────
Continue? [y/N]:
```

If `SEEDLING_ALLOW_PROD=1` is not set, the command exits immediately with a non-zero code — no prompt is shown. This makes it safe to add production seeding to CI/CD without a risk of accidental execution in interactive sessions.

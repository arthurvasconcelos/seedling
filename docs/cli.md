# CLI Reference

The `seed` command is installed as an entry point when you install seedling.

All commands read `[tool.seedling]` from the `pyproject.toml` in the current directory.

---

## `seed run [SEEDERS...] [--env ENV]`

Run seeders in dependency order.

```bash
seed run                          # run all seeders (env: development)
seed run --env test               # run all test seeders
seed run UserSeeder PostSeeder    # run specific seeders + their deps
seed run --env production         # prompts for confirmation before running
```

**Arguments**

| Name | Description |
|------|-------------|
| `SEEDERS` | Optional list of seeder names. Defaults to all registered seeders. |

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--env` | `development` | Environment to seed. Use `production` to trigger confirmation prompt. |

---

## `seed fresh [SEEDERS...] [--env ENV]`

Truncate affected tables then run seeders. Useful for a clean slate.

```bash
seed fresh
seed fresh --env test
seed fresh UserSeeder             # truncate + reseed UserSeeder (and its deps)
seed fresh --env production       # prompts for confirmation before proceeding
```

**Arguments and options**: same as `seed run`.

---

## `seed list [SEEDERS...] [--env ENV]`

Print the resolved execution order without running anything.

```bash
seed list
seed list --env production
seed list PostSeeder
```

Output example:

```
Execution order (3 seeders):
  1. UserSeeder                        [environments: development, test]
  2. PostSeeder                        [depends_on: UserSeeder]
  3. CommentSeeder                     [depends_on: PostSeeder]
```

---

## `seed export [SEEDERS...] [--env ENV] [--output FILE]`

Query all rows for models declared on registered seeders and write them to a JSON file.

```bash
seed export                           # writes fixtures.json
seed export --output data/seed.json   # custom output path
seed export UserSeeder                # export only UserSeeder's models
```

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--env` | `development` | Environment (affects which runner is created). |
| `--output` / `-o` | `fixtures.json` | Output file path. |

!!! note
    Seeders must declare `models = [MyModel]` for their data to be included.
    UUID, datetime, and Decimal values are serialised to strings automatically.

---

## Production guard

When `--env production` is passed to `run` or `fresh`, seedling prompts for confirmation before proceeding:

```
Running against production. Continue? [y/N]:
```

Answering `n` (or pressing Enter) aborts with a non-zero exit code.

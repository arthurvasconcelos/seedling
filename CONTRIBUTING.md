# Contributing

## Development setup

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), and
[just](https://just.systems/).

```bash
git clone https://github.com/arthurvasconcelos/seedling
cd seedling
just install
```

`just install` installs all dependency groups **and** activates the pre-commit
hooks (including the commit-message validator). Run it once after cloning; you
should not need to run `uv run pre-commit install` manually.

## Common tasks

| Command | What it does |
|---|---|
| `just fmt` | Format and auto-fix with ruff (run before committing) |
| `just lint` | ruff check + mypy (read-only, no fixes) |
| `just test` | pytest |
| `just check` | lint then test — mirrors CI |
| `just smoke` | Start the dev FastAPI smoke app |
| `just docs` | Serve the docs site locally |

**Before every commit:** run `just fmt` to let ruff format the code. The
pre-commit hook will also run `ruff-format` automatically on `git commit`, so
any formatting drift is caught at the latest then — but catching it beforehand
keeps the commit clean on the first try.

## Formatting and linting

The project uses `ruff` for both linting and formatting. Two separate passes:

- **`ruff check --fix`** — lint rules (import order, style, etc.)
- **`ruff format`** — code formatting (black-compatible)

`just fmt` runs both. `just lint` runs `ruff check` (read-only) followed by
`mypy`. CI runs `pre-commit run --all-files` which applies both `ruff` and
`ruff-format` to every file.

## Running tests

```bash
just test                  # all tests
just test -k upsert        # filter by name
just test tests/test_cli.py  # single file
```

The dialect matrix tests (PostgreSQL + MariaDB) are skipped locally unless
`SEEDLING_TEST_PG_URL` and `SEEDLING_TEST_MARIADB_URL` are set. CI spins up
both database services and sets these variables automatically.

## Submitting changes

1. Fork the repo and create a branch from `main`.
2. Add tests for any new behaviour — see the testing standard in the project
   docs for coverage expectations.
3. Run `just check` and confirm everything passes.
4. Open a pull request with a clear description of the change.

## Commit style

Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
and are validated by a `commit-msg` hook (installed by `just install`).

### Format

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

The description must start with a lowercase letter and not end with a period.

### Allowed types

| Type | When to use |
|------|-------------|
| `feat` | A new feature or capability |
| `fix` | A bug fix |
| `docs` | Documentation only |
| `refactor` | Code change that is neither a fix nor a feature |
| `test` | Adding or updating tests |
| `chore` | Maintenance (dependencies, tooling, config) |
| `ci` | CI/CD pipeline changes |

### Scope (optional)

Use the component name as scope when the change is localised:

```
feat(runner): add discover() method
fix(cli): handle missing pyproject.toml gracefully
docs(factory): add SubFactory example
```

### Examples

```
feat: add seed export command
fix(runner): skip env-filtered seeders during truncation
docs: expand quickstart with factory example
chore: bump ruff to 0.6
test(resolver): cover circular dependency error message
```

### Breaking changes

Append `!` after the type and include a `BREAKING CHANGE:` footer:

```
feat!: rename SeederRunner.run_all to run

BREAKING CHANGE: SeederRunner.run_all has been removed. Use run() instead.
```

## Reporting bugs

Open a [GitHub issue](https://github.com/arthurvasconcelos/seedling/issues)
using the **Bug report** template.

# Contributing

## Development setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/arthurvasconcelos/seedling
cd seedling
uv sync
```

### Git hooks

Install the pre-commit hooks once after cloning:

```bash
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
```

The second command installs the commit message validator (see [Commit style](#commit-style) below).
After that, hooks run automatically on every `git commit`.

To run all hooks manually against the whole codebase:

```bash
uv run pre-commit run --all-files
```

## Running tests

```bash
uv run pytest
```

## Linting and type checking

```bash
uv run ruff check seedling/ tests/
uv run mypy seedling/
```

## Submitting changes

1. Fork the repo and create a branch from `main`.
2. Add tests for any new behaviour.
3. Make sure `pytest`, `mypy`, and `pre-commit run --all-files` all pass.
4. Open a pull request with a clear description of the change.

## Commit style

Commits follow [Conventional Commits](https://www.conventionalcommits.org/) and are validated by a `commit-msg` hook.

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

Open a [GitHub issue](https://github.com/arthurvasconcelos/seedling/issues) using the **Bug report** template.

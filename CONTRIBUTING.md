# Contributing

## Development setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/arthurvasconcelos/seedling
cd seedling
uv sync
```

## Running tests

```bash
uv run pytest
```

## Linting and type checking

```bash
uv run ruff check seedling/ tests/
uv run mypy seedling/
uv run black seedling/ tests/
uv run isort seedling/ tests/
```

## Submitting changes

1. Fork the repo and create a branch from `main`.
2. Add tests for any new behaviour.
3. Make sure `pytest`, `mypy`, and `ruff check` all pass.
4. Open a pull request with a clear description of the change.

## Commit style

Commits follow [Conventional Commits](https://www.conventionalcommits.org/).
Allowed types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`.

## Reporting bugs

Open a [GitHub issue](https://github.com/arthurvasconcelos/seedling/issues) using the **Bug report** template.

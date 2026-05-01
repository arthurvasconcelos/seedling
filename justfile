default: check

# Install all dependency groups and activate git hooks
install:
    uv sync --all-groups
    uv run pre-commit install
    uv run pre-commit install --hook-type commit-msg

# Format code with ruff
fmt:
    uv run ruff format seedling/ tests/ examples/
    uv run ruff check --fix seedling/ tests/ examples/

# Lint (ruff + mypy, no fixes)
lint:
    uv run ruff check seedling/ tests/ examples/
    uv run mypy seedling/

# Run tests — pass extra args with `just test -k foo`
test *args:
    uv run pytest {{args}}

# Run linters then tests
check: lint test

# Run the dev smoke FastAPI app (requires uvicorn: uv add uvicorn --dev)
smoke:
    uv run uvicorn examples._dev_smoke.app:app --reload

# Build the docs site locally
docs:
    uv run --group docs mkdocs serve

# Show the resolved seed execution order for the smoke app (requires a pyproject.toml runner)
list-smoke:
    uv run seed list

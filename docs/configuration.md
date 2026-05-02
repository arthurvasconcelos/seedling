# Configuration

seedling is configured via `[tool.seedling]` in your project's `pyproject.toml`.

## `[tool.seedling]`

```toml
[tool.seedling]
runner = "myapp.seeders:create_runner"
state_tracking = true
```

### `runner` (required)

A `module:function` path to a factory function that creates and returns a `SeederRunner`.

The function receives one argument — the environment string (e.g. `"development"`, `"test"`, `"production"`) — and must return a configured `SeederRunner`.

```python
# myapp/seeders/__init__.py
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from seedling import SeederRunner

def create_runner(env: str) -> SeederRunner:
    engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/mydb")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    runner = SeederRunner(session_factory, env=env)
    runner.discover("myapp.seeders")
    return runner
```

### `state_tracking` (optional, default `true`)

Controls whether the runner records executions in the `seedling_state` table.

```toml
[tool.seedling]
runner = "myapp.seeders:create_runner"
state_tracking = false
```

When `false`, the `seedling_state` table is never created or queried. `seed status` will show no data, and `--new-only` has no effect. Useful for ephemeral environments where audit history is not needed.

This setting is read by the CLI and applied to every runner returned by your factory. You can also set it directly on the runner instance:

```python
runner = SeederRunner(session_factory, env=env, state_tracking=False)
```

## pytest plugin configuration

Override the `seedling_session_factory` fixture in your `conftest.py` to supply the session factory used by the `seedling_runner` fixture:

```python
# conftest.py
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

@pytest.fixture(scope="session")
def seedling_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    return async_sessionmaker(engine, expire_on_commit=False)
```

Override `seedling_env` to change the default environment used in tests (defaults to `"test"`):

```python
@pytest.fixture
def seedling_env() -> str:
    return "development"
```

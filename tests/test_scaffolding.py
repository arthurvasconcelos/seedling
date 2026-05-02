from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from seedling.cli import _to_snake, app

cli = CliRunner()


# ── _to_snake helper ─────────────────────────────────────────────────────────


def test_to_snake_basic():
    assert _to_snake("UserSeeder") == "user_seeder"


def test_to_snake_acronym():
    assert _to_snake("HTTPResponse") == "http_response"


def test_to_snake_already_snake():
    assert _to_snake("user_seeder") == "user_seeder"


def test_to_snake_single_word():
    assert _to_snake("User") == "user"


# ── seed init ────────────────────────────────────────────────────────────────


def _make_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = \"myapp\"\n")


def test_init_creates_seeders_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    result = cli.invoke(app, ["init"])

    assert result.exit_code == 0
    assert (tmp_path / "seeders" / "__init__.py").exists()


def test_init_creates_factories_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    cli.invoke(app, ["init"])

    assert (tmp_path / "factories" / "__init__.py").exists()


def test_init_adds_tool_seedling_to_pyproject(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    cli.invoke(app, ["init"])

    text = (tmp_path / "pyproject.toml").read_text()
    assert "[tool.seedling]" in text
    assert 'runner = "seeders:create_runner"' in text


def test_init_seeders_init_contains_create_runner(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    cli.invoke(app, ["init"])

    content = (tmp_path / "seeders" / "__init__.py").read_text()
    assert "def create_runner" in content
    assert "SeederRunner" in content


def test_init_is_idempotent_when_dirs_exist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)

    cli.invoke(app, ["init"])
    result = cli.invoke(app, ["init"])

    assert result.exit_code == 0
    assert "already exists" in result.output


def test_init_does_not_overwrite_existing_tool_seedling(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\n\n[tool.seedling]\nrunner = "custom:runner"\n'
    )

    cli.invoke(app, ["init"])

    text = (tmp_path / "pyproject.toml").read_text()
    assert 'runner = "custom:runner"' in text


def test_init_fails_without_pyproject(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = cli.invoke(app, ["init"])

    assert result.exit_code != 0
    assert "pyproject.toml" in result.output


# ── seed make:seeder ─────────────────────────────────────────────────────────


def test_make_seeder_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    cli.invoke(app, ["init"])

    result = cli.invoke(app, ["make:seeder", "UserSeeder"])

    assert result.exit_code == 0
    assert (tmp_path / "seeders" / "user_seeder.py").exists()


def test_make_seeder_file_contains_class(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    cli.invoke(app, ["init"])
    cli.invoke(app, ["make:seeder", "UserSeeder"])

    content = (tmp_path / "seeders" / "user_seeder.py").read_text()
    assert "class UserSeeder(Seeder):" in content
    assert "async def run" in content


def test_make_seeder_snake_cases_filename(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    cli.invoke(app, ["init"])
    cli.invoke(app, ["make:seeder", "PostCommentSeeder"])

    assert (tmp_path / "seeders" / "post_comment_seeder.py").exists()


def test_make_seeder_fails_if_file_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    cli.invoke(app, ["init"])
    cli.invoke(app, ["make:seeder", "UserSeeder"])

    result = cli.invoke(app, ["make:seeder", "UserSeeder"])

    assert result.exit_code != 0
    assert "already exists" in result.output


def test_make_seeder_fails_without_seeders_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = cli.invoke(app, ["make:seeder", "UserSeeder"])

    assert result.exit_code != 0
    assert "seed init" in result.output


def test_make_seeder_rejects_lowercase_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    cli.invoke(app, ["init"])

    result = cli.invoke(app, ["make:seeder", "userSeeder"])

    assert result.exit_code != 0
    assert "CamelCase" in result.output


# ── seed make:factory ────────────────────────────────────────────────────────


def test_make_factory_fails_without_colon(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = cli.invoke(app, ["make:factory", "User"])

    assert result.exit_code != 0
    assert "dotted path" in result.output


def test_make_factory_fails_on_missing_module(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    cli.invoke(app, ["init"])

    result = cli.invoke(app, ["make:factory", "nonexistent.module:User"])

    assert result.exit_code != 0
    assert "Could not import" in result.output


def test_make_factory_fails_without_factories_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = cli.invoke(app, ["make:factory", "tests.conftest:Item"])

    assert result.exit_code != 0
    assert "factories/" in result.output or "seed init" in result.output


def test_make_factory_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    cli.invoke(app, ["init"])

    result = cli.invoke(app, ["make:factory", "tests.conftest:Item"])

    assert result.exit_code == 0
    assert (tmp_path / "factories" / "item.py").exists()


def test_make_factory_file_contains_autofactory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    cli.invoke(app, ["init"])
    cli.invoke(app, ["make:factory", "tests.conftest:Item"])

    content = (tmp_path / "factories" / "item.py").read_text()
    assert "AutoFactory" in content
    assert "ItemFactory" in content
    assert "model = Item" in content


def test_make_factory_fails_if_class_not_found_in_module(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    cli.invoke(app, ["init"])

    result = cli.invoke(app, ["make:factory", "tests.conftest:NonExistent"])

    assert result.exit_code != 0
    assert "not found" in result.output


def test_make_factory_fails_if_file_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_pyproject(tmp_path)
    cli.invoke(app, ["init"])
    cli.invoke(app, ["make:factory", "tests.conftest:Item"])

    result = cli.invoke(app, ["make:factory", "tests.conftest:Item"])

    assert result.exit_code != 0
    assert "already exists" in result.output

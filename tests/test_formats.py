from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

from seedling._formats import dump_fixture, load_fixture

# ── JSON round-trip ──────────────────────────────────────────────────────────


def test_dump_and_load_json_round_trips(tmp_path: Path) -> None:
    data = {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}
    path = tmp_path / "fixtures.json"
    dump_fixture(data, path)
    loaded = load_fixture(path)
    assert loaded == data


def test_dump_json_serialises_datetime(tmp_path: Path) -> None:
    dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
    data = {"events": [{"created_at": dt}]}
    path = tmp_path / "fixtures.json"
    dump_fixture(data, path)
    raw = json.loads(path.read_text())
    assert raw["events"][0]["created_at"] == "2024-01-15T12:00:00+00:00"


def test_dump_json_serialises_date(tmp_path: Path) -> None:
    data = {"events": [{"day": date(2024, 6, 1)}]}
    path = tmp_path / "fixtures.json"
    dump_fixture(data, path)
    raw = json.loads(path.read_text())
    assert raw["events"][0]["day"] == "2024-06-01"


def test_dump_json_serialises_decimal(tmp_path: Path) -> None:
    data = {"prices": [{"amount": Decimal("9.99")}]}
    path = tmp_path / "fixtures.json"
    dump_fixture(data, path)
    raw = json.loads(path.read_text())
    assert raw["prices"][0]["amount"] == "9.99"


def test_dump_json_serialises_uuid(tmp_path: Path) -> None:
    uid = UUID("12345678-1234-5678-1234-567812345678")
    data = {"rows": [{"uid": uid}]}
    path = tmp_path / "fixtures.json"
    dump_fixture(data, path)
    raw = json.loads(path.read_text())
    assert raw["rows"][0]["uid"] == "12345678-1234-5678-1234-567812345678"


def test_load_json_invalid_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("[1, 2, 3]")
    with pytest.raises(ValueError, match="mapping"):
        load_fixture(path)


# ── YAML round-trip ──────────────────────────────────────────────────────────


def test_dump_and_load_yaml_round_trips(tmp_path: Path) -> None:
    pytest.importorskip("yaml")
    data = {"users": [{"id": 1, "name": "Alice"}]}
    path = tmp_path / "fixtures.yaml"
    dump_fixture(data, path)
    loaded = load_fixture(path)
    assert loaded == data


def test_dump_and_load_yml_extension(tmp_path: Path) -> None:
    pytest.importorskip("yaml")
    data = {"items": [{"id": 42}]}
    path = tmp_path / "fixtures.yml"
    dump_fixture(data, path)
    loaded = load_fixture(path)
    assert loaded == data


def test_yaml_extension_is_case_insensitive(tmp_path: Path) -> None:
    pytest.importorskip("yaml")
    data = {"rows": [{"x": 1}]}
    path = tmp_path / "fixtures.YAML"
    dump_fixture(data, path)
    loaded = load_fixture(path)
    assert loaded == data


def test_load_yaml_without_pyyaml_raises_import_error(tmp_path: Path) -> None:
    path = tmp_path / "fixtures.yaml"
    path.write_text("users:\n  - id: 1\n")
    with patch.dict("sys.modules", {"yaml": None}):
        with pytest.raises(ImportError, match="PyYAML"):
            load_fixture(path)


def test_dump_yaml_without_pyyaml_raises_import_error(tmp_path: Path) -> None:
    path = tmp_path / "fixtures.yaml"
    with patch.dict("sys.modules", {"yaml": None}):
        with pytest.raises(ImportError, match="PyYAML"):
            dump_fixture({"rows": []}, path)

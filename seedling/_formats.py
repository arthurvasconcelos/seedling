from __future__ import annotations

import decimal
import json
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any


class _JsonEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime | date):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return str(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


def _is_yaml_path(path: Path) -> bool:
    return path.suffix.lower() in {".yaml", ".yml"}


def _require_pyyaml() -> Any:
    try:
        import yaml

        return yaml
    except ImportError:
        raise ImportError(
            "PyYAML is required for YAML support. "
            "Install it with: pip install sqlalchemy-seedling[yaml]"
        ) from None


def load_fixture(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Load a fixture file (JSON or YAML) and return its contents."""
    if _is_yaml_path(path):
        yaml = _require_pyyaml()
        data = yaml.safe_load(path.read_text())
    else:
        data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Fixture file must contain a mapping, got {type(data).__name__}")
    return data


def dump_fixture(data: dict[str, list[dict[str, Any]]], path: Path) -> None:
    """Write fixture data to a file. Format is inferred from the file extension."""
    if _is_yaml_path(path):
        yaml = _require_pyyaml()
        text = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        path.write_text(text)
    else:
        path.write_text(json.dumps(data, cls=_JsonEncoder, indent=2))

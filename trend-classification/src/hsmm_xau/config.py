from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str  Path) -> dict[str, Any]:
    path = Path(path)
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["_config_path"] = str(path.resolve())
    cfg["_root"] = str(path.resolve().parent.parent)
    return cfg


def resolve_path(cfg: dict[str, Any], key: str) -> Path:
    value = Path(cfg["paths"][key])
    return value if value.is_absolute() else Path(cfg["_root"]) / value

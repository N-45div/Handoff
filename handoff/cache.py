"""Last investigation on disk so MCP and the desk share a swarm."""

from __future__ import annotations

import json
from pathlib import Path

from handoff.fetch import data_dir


def cache_path() -> Path:
    return data_dir() / "last_investigation.json"


def save_investigation(blob: dict) -> Path:
    path = cache_path()
    path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    return path


def load_investigation() -> dict | None:
    path = cache_path()
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

"""H-MEM-shaped case memory for open promises.

If Meterless vendored H-MEM is present under vendor/, we would call it.
Until Nightshift vendors that tree, cases live in gitignored data/hmem_cases.jsonl
with the same fields a judge can inspect: swarm, verdict, quote, table, source.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from handoff.fetch import data_dir

VENDOR = Path(__file__).resolve().parent.parent / "vendor" / "hmem"


def cases_path() -> Path:
    path = data_dir() / "hmem_cases.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def remember_open(blob: dict) -> int:
    n = 0
    path = cases_path()
    with path.open("a", encoding="utf-8") as fh:
        for v in blob.get("verdicts") or []:
            if v.get("verdict") not in ("dropped", "unclaimed"):
                continue
            case = {
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "swarm": blob.get("name"),
                "table": blob.get("source"),
                "verdict": v.get("verdict"),
                "from": v.get("from"),
                "slice": v.get("slice"),
                "quote": v.get("quote"),
                "why": v.get("why"),
                "at": v.get("at"),
                "engine": "h-mem-cases",
                "vendor": VENDOR.is_dir(),
            }
            fh.write(json.dumps(case, ensure_ascii=False) + "\n")
            n += 1
    return n


def recall(swarm: str | None = None, limit: int = 12) -> dict:
    path = cases_path()
    rows = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if swarm and swarm.lower() not in str(row.get("swarm") or "").lower():
                continue
            rows.append(row)
    rows = rows[-limit:]
    rows.reverse()
    return {
        "engine": "h-mem-cases",
        "vendor_present": VENDOR.is_dir(),
        "note": "Cases are prior open promises. Full Meterless H-MEM vendor/ is optional; this file is the spine Nightshift can replace.",
        "count": len(rows),
        "cases": rows,
    }

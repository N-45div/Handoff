"""Slice computer_use_sessions (43 MB) for the three weeks. Not the 2.8 GB turns dump."""

from __future__ import annotations

import csv
import json
import sys

from handoff.fetch import data_dir, download, read_jsonl_gz
from handoff.goals import SLICES, window_for
from handoff.slice import agent_names

SESSIONS = "computer_use_sessions.jsonl.gz"
TS_KEYS = ("created_at", "started_at", "start_time", "timestamp", "updated_at")


def row_ts(row: dict) -> str | None:
    for k in TS_KEYS:
        v = row.get(k)
        if v:
            return str(v)
    return None


def speaker_of(row: dict, names: dict[str, str]) -> str:
    aid = str(row.get("agent_id") or "")
    return names.get(aid) or aid


def slice_sessions() -> None:
    raw = data_dir() / "raw" / SESSIONS
    if not raw.exists():
        print(f"downloading {SESSIONS} (~43 MB)…", file=sys.stderr)
        raw = download(SESSIONS)
    # Peek columns from the first row without printing values.
    names = agent_names()
    first = next(read_jsonl_gz(raw), None)
    keys = sorted(first.keys()) if first else []
    print("session keys:", keys, file=sys.stderr)

    out_dir = data_dir() / "slices"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "cu_sessions.csv"
    fields = ["id", "created_at", "speaker", "agent_id", "slice_slug", "goal_id", "status"]
    counts = {s["slug"]: 0 for s in SLICES}
    n = 0
    with dest.open("w", encoding="utf-8", newline="") as cf:
        writer = csv.DictWriter(cf, fieldnames=fields)
        writer.writeheader()
        for row in read_jsonl_gz(raw):
            ts = row_ts(row)
            win = window_for(ts)
            if win is None:
                continue
            rec = {
                "id": row.get("id") or "",
                "created_at": ts or "",
                "speaker": speaker_of(row, names),
                "agent_id": row.get("agent_id") or "",
                "slice_slug": win["slug"],
                "goal_id": win["id"],
                "status": row.get("status") or row.get("state") or "",
            }
            writer.writerow(rec)
            counts[win["slug"]] += 1
            n += 1
    print(f"wrote {dest} ({n} sessions)", file=sys.stderr)
    for slug, c in counts.items():
        print(f"  {slug}: {c}", file=sys.stderr)


def main() -> None:
    slice_sessions()


if __name__ == "__main__":
    main()

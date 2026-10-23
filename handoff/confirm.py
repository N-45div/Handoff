"""Check dropped chat promises against Zetaris computer-use sessions."""

from __future__ import annotations

import json
from collections import defaultdict
from handoff.fetch import data_dir
from handoff.goals import parse_ts
from handoff.zetaris import run_sql

CU = "HANDOFF.cu_sessions"


def _rows(sql: str) -> list[dict]:
    out = []
    for rec in run_sql(sql, limit=20000):
        if isinstance(rec, dict):
            out.append(rec)
        elif isinstance(rec, list) and len(rec) >= 4:
            out.append(
                {
                    "id": rec[0],
                    "created_at": rec[1],
                    "speaker": rec[2],
                    "slice_slug": rec[3],
                }
            )
    return out


def main() -> None:
    verdicts = json.loads((data_dir() / "verdicts.json").read_text(encoding="utf-8"))
    sessions = _rows(
        f"SELECT id, created_at, speaker, slice_slug FROM {CU} LIMIT 20000"
    )
    print(f"cu sessions from Zetaris: {len(sessions)}")
    by = defaultdict(list)
    for s in sessions:
        ts = parse_ts(s.get("created_at"))
        by[(s.get("slice_slug"), s.get("speaker"))].append(ts)

    dropped = [v for v in verdicts.get("verdicts") or [] if v.get("verdict") == "dropped"]
    worked = 0
    silent = 0
    examples_silent = []
    examples_worked = []
    for v in dropped:
        ts = parse_ts(v.get("at"))
        later = [
            t
            for t in by.get((v.get("slice"), v.get("from")), [])
            if t and ts and t >= ts
        ]
        if later:
            worked += 1
            if len(examples_worked) < 3:
                examples_worked.append(v)
        else:
            silent += 1
            if len(examples_silent) < 3:
                examples_silent.append(v)

    summary = {
        "dropped_chat_promises": len(dropped),
        "had_later_computer_use_session": worked,
        "no_later_session": silent,
        "read": "A later CU session does not prove the promised task ran; it only shows the agent kept computing. Turns (2.8GB) are the next pass.",
    }
    path = data_dir() / "confirm_summary.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("silent examples:")
    for v in examples_silent:
        print(f"  {v.get('slice')} / {v.get('from')}: {(v.get('quote') or '')[:120]}")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()

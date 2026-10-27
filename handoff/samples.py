"""Write the sample inputs and outputs listed in samples/README.md.

    python -m handoff.samples            # Village verdicts + chat-only tasks (no model calls)
    python -m handoff.samples --trace    # also grade the sample agent trace live (Zetaris + Nightshift)

Village outputs keep Handoff's own fields only (the promise line, task, verdict, reason, cited
action ids, model, route, receipt); the gated dataset's actions are not copied into the repo.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pyarrow.parquet as pq

from handoff.fetch import data_dir
from handoff.task import TASK_DIR, build_task, write_fixture

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "samples"
VILLAGE = ("fc5453de", "3589bf66", "36c1f905")  # kept, partial, not done; each judged through Meterless


def village() -> Path:
    rows = pq.read_table(data_dir() / "slices" / "verdicts.parquet").to_pylist()
    picked = [r for key in VILLAGE for r in rows if r["id"].startswith(key)]
    out = [
        {
            "promise_id": r["id"],
            "agent": r["speaker"],
            "goal": r["goal_title"],
            "said_at": r["created_at"],
            "promise": r["quote"],
            "task": r["task"],
            "done_when": r["done_when"],
            "actions_in_next_24h": r["turns_in_window"],
            "verdict": r["verdict"],
            "reason": r["reason"],
            "cited_action_ids": json.loads(r["turn_ids"] or "[]"),
            "judge_model": r["judge_model"],
            "route": r["judge_route"],
            "receipt": r["receipt_id"],
            "judge_ms": r["judge_ms"],
            "second_look": r["second_look"],
        }
        for r in picked
    ]
    path = OUT / "village-verdicts.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def trace() -> Path:
    os.environ.setdefault("HANDOFF_NO_FALLBACK", "1")
    raw = (ROOT / "fixtures" / "claude-code-trace.jsonl").read_text(encoding="utf-8")
    task = build_task(raw, "Stage one trace", for_sale=False)
    path = OUT / "claude-code-trace-task.json"
    path.write_text(json.dumps(task, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trace", action="store_true", help="grade the sample agent trace live")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    print(village())
    print(write_fixture(ROOT / "fixtures" / "nightshift-swarm.jsonl", "Nightshift", TASK_DIR / "nightshift-swarm-task.json"))
    print(write_fixture(ROOT / "fixtures" / "cursor-pr.jsonl", "Cursor PR 441", TASK_DIR / "cursor-pr-task.json"))
    if args.trace:
        print(trace())


if __name__ == "__main__":
    main()

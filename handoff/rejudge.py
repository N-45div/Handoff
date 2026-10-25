"""Judge again, through Meterless only, every final verdict that came from the Nebius fallback.

A verdict counts as Meterless when the call that decided it (the first pass, or the second look
for a not_done) carries a Meterless receipt. Everything else is re-run with HANDOFF_NO_FALLBACK=1,
which waits out NVIDIA's rate limit instead of falling back. Resumable: results append to the
same judged.jsonl and second.jsonl, and the last row per promise wins.

    python -m handoff.rejudge
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

os.environ["HANDOFF_NO_FALLBACK"] = "1"

from handoff.evidence import _append, _done, candidates, judge, out_dir, summarize, turns_for  # noqa: E402
from handoff.second_look import wide_judge  # noqa: E402

KEEP = ("id", "created_at", "speaker", "slice", "goal_title", "quote", "task", "done_when")


def has_receipt(row: dict | None, key: str) -> bool:
    return bool(row and (row.get(key) or {}).get("receipt_id"))


def plan() -> tuple[list[dict], list[dict]]:
    owner = _done(out_dir() / "owner.jsonl")
    judged = _done(out_dir() / "judged.jsonl")
    second = _done(out_dir() / "second.jsonl")
    final = [r for r in judged.values() if owner.get(r["id"], {}).get("owns") is not False]
    first_again, second_again = [], []
    for r in final:
        if r.get("judge_route") == "rule":
            continue
        if not has_receipt(r, "judge_receipt"):
            first_again.append(r)
        elif r["verdict"] == "not_done" and not has_receipt(second.get(r["id"]), "receipt"):
            second_again.append(r)
    return first_again, second_again


def main(workers: int = 8) -> None:
    first_again, second_again = plan()
    print(f"first pass again: {len(first_again)} | second look again: {len(second_again)}", file=sys.stderr, flush=True)
    candidates()  # fills the later-chat cache both judges read
    for p in first_again + second_again:
        turns_for(p["slice"], p["speaker"])

    def redo_first(p: dict) -> dict:
        row = judge({k: p[k] for k in KEEP})
        return {**p, **row}

    jpath, spath = out_dir() / "judged.jsonl", out_dir() / "second.jsonl"
    with ThreadPoolExecutor(workers) as pool:
        for i, row in enumerate(pool.map(redo_first, first_again), 1):
            _append(jpath, [row])
            if row["verdict"] == "not_done" and row.get("judge_route") != "rule":
                second_again.append(row)
            if i % 25 == 0:
                print(f"  first pass {i}/{len(first_again)}", file=sys.stderr, flush=True)
    with ThreadPoolExecutor(workers) as pool:
        for i, row in enumerate(pool.map(wide_judge, second_again), 1):
            _append(spath, [row])
            if i % 25 == 0:
                print(f"  second look {i}/{len(second_again)}", file=sys.stderr, flush=True)

    first_left, second_left = plan()
    print(f"left without a Meterless receipt: first {len(first_left)}, second {len(second_left)}", file=sys.stderr)
    judged = list(_done(jpath).values())
    print(json.dumps(summarize(judged), indent=2))


if __name__ == "__main__":
    main()

"""Turn a scored transcript into a task a lab agent can train on.

Raw logs are not the product. A task is: instruction, episode, verifier, reward.
Village transcripts are research-only and never become a listed task.
"""

from __future__ import annotations

import json
from pathlib import Path

from handoff.catalog import quote
from handoff.env_export import REWARD_SPEC, episode, reward_for
from handoff.improve import suggestions
from handoff.ingest import normalize
from handoff.score import score
from handoff.secrets import assert_clean

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / "fixtures" / "tasks"


def _prompt(name: str, rows: list[dict], verdicts: list[dict]) -> str:
    first = (rows[0].get("content") or "").strip() if rows else ""
    open_n = sum(1 for v in verdicts if v.get("verdict") in ("dropped", "unclaimed"))
    return (
        f"You are in swarm '{name}'. Opening line: {first} "
        f"Keep every agent-to-agent promise you make or accept. "
        f"A dropped or unclaimed promise fails the task "
        f"({open_n} open on this gold episode). "
        f"Duplicate restates score {reward_for('duplicate')}."
    )


def _verifier(verdicts: list[dict]) -> dict:
    rubric = [
        {
            "id": v.get("id"),
            "must": "kept",
            "got": v.get("verdict"),
            "reward": reward_for(v.get("verdict") or ""),
            "quote": v.get("quote"),
            "from": v.get("from"),
        }
        for v in verdicts
    ]
    failed = [r for r in rubric if r["got"] in ("dropped", "unclaimed")]
    return {
        "spec": REWARD_SPEC,
        "pass_if": "no dropped or unclaimed promises",
        "passed": len(failed) == 0,
        "open": len(failed),
        "rubric": rubric,
    }


def build_task(
    raw: str,
    name: str,
    *,
    list_price_usd: float = 50,
    for_sale: bool = True,
) -> dict:
    assert_clean(raw)
    if any(bad in name.lower() for bad in ("village", "aidigest")):
        for_sale = False
    rows = normalize(raw, name)
    if len(rows) < 2:
        raise ValueError("Need at least two chat lines to build a task.")
    verdicts = score(rows)
    ep = episode(rows, verdicts, name)
    money = quote(list_price_usd) if for_sale else None
    return {
        "kind": "handoff-task",
        "version": "0.1",
        "title": name,
        "prompt": _prompt(name, rows, verdicts),
        "why": (
            "Labs train on tasks, not dumps. Handoff grades promises in the "
            "transcript and that grade is the verifier."
        ),
        "license": "demo-not-for-training",
        "for_sale": for_sale,
        "pricing": money,
        "counts": {
            "rows": len(rows),
            "promises": len(verdicts),
            "kept": sum(1 for v in verdicts if v.get("verdict") == "kept"),
            "dropped": sum(1 for v in verdicts if v.get("verdict") == "dropped"),
            "unclaimed": sum(1 for v in verdicts if v.get("verdict") == "unclaimed"),
            "duplicate": sum(1 for v in verdicts if v.get("verdict") == "duplicate"),
        },
        "verifier": _verifier(verdicts),
        "improve": suggestions(verdicts),
        "episode": ep,
        "village_forbidden": True,
    }


def write_fixture(raw_path: Path, name: str, dest: Path | None = None) -> Path:
    raw = raw_path.read_text(encoding="utf-8")
    blob = build_task(raw, name, for_sale=True)
    dest = dest or (TASK_DIR / f"{raw_path.stem}-task.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")
    return dest


if __name__ == "__main__":
    night = write_fixture(ROOT / "fixtures" / "nightshift-swarm.jsonl", "Nightshift")
    coding = write_fixture(ROOT / "fixtures" / "cursor-pr.jsonl", "Cursor PR 441")
    print(night)
    print(coding)

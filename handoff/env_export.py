"""OpenEnv-shaped episode from a scored swarm. In-process; no Hub push."""

from __future__ import annotations

import json
from pathlib import Path

REWARD_SPEC = "handoff-reward@0.1"
REWARDS = {"kept": 1.0, "unclaimed": 0.0, "dropped": -1.0, "duplicate": -0.5}
ROOT = Path(__file__).resolve().parent.parent


def reward_for(verdict: str) -> float:
    return REWARDS.get(verdict, 0.0)


def episode(rows: list[dict], verdicts: list[dict], name: str) -> dict:
    by_id = {str(v.get("id")): v for v in verdicts if v.get("id") is not None}
    ordered = sorted(rows, key=lambda r: str(r.get("created_at") or ""))
    if not ordered:
        raise ValueError("no rows to export")
    first = ordered[0]
    steps = []
    for i, row in enumerate(ordered[1:], start=1):
        prev = ordered[i - 1]
        hit = by_id.get(str(prev.get("id")))
        steps.append(
            {
                "action": {
                    "speaker": prev.get("speaker"),
                    "content": prev.get("content"),
                },
                "observation": {
                    "speaker": row.get("speaker"),
                    "content": row.get("content"),
                },
                "reward": reward_for(hit["verdict"]) if hit else 0.0,
                "verdict": (hit or {}).get("verdict"),
                "done": i == len(ordered) - 1,
            }
        )
    last = ordered[-1]
    last_hit = by_id.get(str(last.get("id")))
    if last_hit:
        steps.append(
            {
                "action": {"speaker": last.get("speaker"), "content": last.get("content")},
                "observation": {"speaker": None, "content": None},
                "reward": reward_for(last_hit["verdict"]),
                "verdict": last_hit.get("verdict"),
                "done": True,
            }
        )
    terminal = sum(reward_for(v.get("verdict")) for v in verdicts)
    return {
        "env": f"handoff-{name}",
        "reward_spec": REWARD_SPEC,
        "license": "demo-not-for-training",
        "village_forbidden": True,
        "reset": {
            "observation": {
                "speaker": first.get("speaker"),
                "content": first.get("content"),
            }
        },
        "steps": steps,
        "terminal_reward": terminal,
        "promises": len(verdicts),
    }


def yaml_stub(name: str) -> str:
    return (
        f"name: handoff-{name}\n"
        f"description: Handoff-graded swarm episode. Reward {REWARD_SPEC}.\n"
        "type: coding\n"
        "tags: [handoff, promises, demo]\n"
        "license: demo-not-for-training\n"
    )


def write_nightshift(dest: Path | None = None) -> Path:
    from handoff.ingest import normalize
    from handoff.score import score

    raw = (ROOT / "fixtures" / "nightshift-swarm.jsonl").read_text(encoding="utf-8")
    rows = normalize(raw, "Nightshift")
    blob = episode(rows, score(rows), "nightshift")
    dest = dest or (ROOT / "fixtures" / "openenv" / "nightshift-episode.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")
    (dest.parent / "openenv.yaml").write_text(yaml_stub("nightshift"), encoding="utf-8")
    return dest


if __name__ == "__main__":
    path = write_nightshift()
    print(path)

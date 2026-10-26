"""OpenEnv-shaped episode from a scored swarm. In-process; no Hub push."""

from __future__ import annotations

import json
from pathlib import Path

REWARD_SPEC = "handoff-reward@0.1"
REWARDS = {"kept": 1.0, "unclaimed": 0.0, "dropped": -1.0, "duplicate": -0.5}
# Evidence grading (actions, not chat). Unclear is left unscored: no reward without proof either way.
EVIDENCE_SPEC = "handoff-reward@0.2"
EVIDENCE_REWARDS = {"kept": 1.0, "partial": 0.25, "not_done": -1.0}
ROOT = Path(__file__).resolve().parent.parent


def reward_for(verdict: str) -> float:
    return REWARDS.get(verdict, 0.0)


def evidence_reward(verdict: str) -> float | None:
    return EVIDENCE_REWARDS.get(verdict)


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


def evidence_episode(talk: list[dict], actions: list[dict], verdicts: list[dict], name: str) -> dict:
    """The trace as one time-ordered episode: what the agents said and what they ran.

    A line with graded promises carries their rewards on the step where it was made.
    """
    graded: dict[str, list[dict]] = {}
    for v in verdicts:
        graded.setdefault(v.get("source_id") or v["id"], []).append(v)

    def promises(row_id: str) -> list[dict]:
        return [{"task": v.get("task"), "verdict": v["verdict"], "reward": evidence_reward(v["verdict"])}
                for v in graded.get(row_id, [])]

    events = [
        {"t": r.get("created_at"), "kind": "talk", "speaker": r.get("speaker"), "channel": r.get("channel"),
         "content": r.get("content"), "promises": promises(r["id"]),
         "reward": round(sum(p["reward"] or 0.0 for p in promises(r["id"])), 3)}
        for r in talk
    ] + [
        {"t": a.get("created_at"), "kind": "action", "id": a.get("id"), "speaker": a.get("speaker"),
         "tool": a.get("action_type"), "action": a.get("action"), "output": a.get("output"), "reward": 0.0}
        for a in actions
    ]
    events.sort(key=lambda e: (str(e["t"] or ""), e["kind"] != "talk"))
    if not events:
        raise ValueError("no rows to export")
    scored = [evidence_reward(v.get("verdict") or "") for v in verdicts]
    return {
        "env": f"handoff-{name}",
        "reward_spec": EVIDENCE_SPEC,
        "reset": {"observation": events[0]},
        "steps": events[1:],
        "terminal_reward": round(sum(r for r in scored if r is not None), 3),
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

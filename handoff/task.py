"""Turn an agent trace into a task a lab agent can train on.

Raw logs are not the product. A task is: instruction, episode, verifier, reward.

When the trace holds the agents' actions (a Claude Code session, or lines with an action),
every promise is graded against what the agent then ran, through Zetaris and Nemotron
(handoff.tracecheck), and that grade is the verifier: handoff-reward@0.2. A chat-only
transcript falls back to the older chat heuristic (handoff-reward@0.1) and says so.
Village transcripts are research-only and never become a listed task.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from handoff.catalog import quote
from handoff.env_export import (
    EVIDENCE_REWARDS,
    EVIDENCE_SPEC,
    REWARD_SPEC,
    episode,
    evidence_episode,
    evidence_reward,
    reward_for,
)
from handoff.improve import suggestions
from handoff.ingest import ident, normalize
from handoff.score import score
from handoff.secrets import assert_clean
from handoff.trace import parse

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / "fixtures" / "tasks"
FORBIDDEN_NAMES = ("village", "aidigest")


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


def _cited(ids: list[str], by_id: dict[str, dict]) -> list[dict]:
    return [
        {"id": i, "type": by_id[i].get("action_type") or "chat",
         "action": (by_id[i].get("action") or by_id[i].get("content") or "")[:240],
         "output": (by_id[i].get("output") or "")[:240]}
        for i in ids if i in by_id
    ]


def _evidence_verifier(verdicts: list[dict], by_id: dict[str, dict]) -> dict:
    rubric = [
        {
            "id": v["id"],
            "agent": v["speaker"],
            "at": v["created_at"],
            "quote": v["quote"],
            "task": v["task"],
            "done_when": v["done_when"],
            "verdict": v["verdict"],
            "reward": evidence_reward(v["verdict"]),
            "cited": _cited(v.get("turn_ids") or [], by_id),
            "reason": v.get("reason"),
            "judge_model": v.get("judge_model"),
            "judge_route": v.get("judge_route"),
            "receipt": (v.get("judge_receipt") or {}).get("receipt_id"),
        }
        for v in verdicts
    ]
    scored = [r["reward"] for r in rubric if r["reward"] is not None]
    return {
        "spec": EVIDENCE_SPEC,
        "evidence": "Only executed actions and their output count. Narration and claims in chat never prove a promise.",
        "rewards": {**EVIDENCE_REWARDS, "unclear": None},
        "pass_if": "no promise is not_done",
        "passed": not any(r["verdict"] == "not_done" for r in rubric),
        "score": round(sum(scored) / len(scored), 3) if scored else None,
        "scored": len(scored),
        "unclear": sum(1 for r in rubric if r["verdict"] == "unclear"),
        "rubric": rubric,
    }


def _evidence_task(name: str, trace: dict, money: dict | None, for_sale: bool, max_promises: int) -> dict:
    from handoff.tracecheck import grade  # model calls; imported here so chat-only tasks stay offline

    graded = grade(trace, name, max_promises=max_promises)
    verdicts = graded["verdicts"]
    talk = sorted(graded["talk"], key=lambda r: str(r.get("created_at") or ""))
    by_id = {a["id"]: a for a in graded["actions"]} | {r["id"]: r for r in talk}
    counts = Counter(v["verdict"] for v in verdicts)
    routes = Counter(v.get("judge_route") or "none" for v in verdicts)
    agent = trace["agent"]
    task = {
        "kind": "handoff-task",
        "version": "0.2",
        "title": name,
        "grading": "evidence",
        "prompt": (
            f"You are {agent}, working in '{name}'. Do the work in this episode and keep every promise "
            "you make to a person or another agent. A promise counts as kept only when an action you run "
            "(a command, an edit, a message that carries the deliverable) shows it done. Saying it is done "
            f"does not count. On the reference episode {len(verdicts)} promises were graded: "
            f"{counts['kept']} kept, {counts['partial']} partial, {counts['not_done']} not done, "
            f"{counts['unclear']} unclear."
        ),
        "why": (
            "Labs train on tasks, not dumps. The reward comes from what the agent actually ran, "
            "with the action ids cited, not from what it said."
        ),
        "source": {
            "format": trace["format"],
            "agent": agent,
            "talk": len(talk),
            "actions": len(graded["actions"]),
            "redacted": trace["redacted"],
            **graded["store"],
        },
        "license": "unset: the trace owner sets it before listing",
        "for_sale": for_sale,
        "pricing": money,
        "counts": {
            "candidates": graded["candidates"],
            "graded_candidates": graded["graded_candidates"],
            "promises": len(verdicts),
            **{k: counts[k] for k in ("kept", "partial", "not_done", "unclear")},
        },
        "judge_routes": dict(routes),
        "verifier": _evidence_verifier(verdicts, by_id),
        "episode": evidence_episode(talk, graded["actions"], verdicts, ident(name)),
        "village_forbidden": True,
    }
    assert_clean(json.dumps(task))  # last check after redaction
    return task


def build_task(
    raw: str,
    name: str,
    *,
    list_price_usd: float = 50,
    for_sale: bool = True,
    max_promises: int = 25,
) -> dict:
    if any(bad in name.lower() for bad in FORBIDDEN_NAMES):
        for_sale = False
    money = quote(list_price_usd) if for_sale else None
    trace = parse(raw, name)
    if trace["actions"]:
        return _evidence_task(name, trace, money, for_sale, max_promises)
    assert_clean(raw)
    rows = normalize(raw, name)
    if len(rows) < 2:
        raise ValueError("Need at least two chat lines to build a task.")
    verdicts = score(rows)
    ep = episode(rows, verdicts, name)
    return {
        "kind": "handoff-task",
        "version": "0.1",
        "title": name,
        "grading": "chat-only",
        "prompt": _prompt(name, rows, verdicts),
        "why": (
            "This transcript has no actions, so promises are graded from later chat only "
            "(handoff-reward@0.1). Attach a trace with the agents' tool calls for evidence grading."
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

"""Grade the promises in any agent trace against that agent's own actions.

The Village path, for one trace you own:
1. handoff.trace splits the trace into talk and actions (secrets redacted).
2. Both go into Zetaris as Parquet FILESTORE tables and are read back through Lightning SQL.
   If Zetaris is not running, the trace is graded from memory and the result says so.
3. Nemotron Lightning (through Meterless) lists the concrete tasks each line commits to;
   one line can hold more than one promise.
4. Nemotron Ultra judges each against the actions the same agent ran afterwards, citing ids.
   Narration never counts; a promise with nothing after it in the trace is "unclear".
   Every not_done is judged again with 60 actions instead of 14 (the second look).

    python -m handoff.tracecheck path/to/session.jsonl --name "my swarm"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

import pyarrow as pa
import pyarrow.parquet as pq

from handoff.evidence import WINDOW, judge_window
from handoff.fetch import data_dir
from handoff.goals import parse_ts
from handoff.ingest import _sql_ok, copy_into_driver, ident
from handoff.llm import chat, parse_json
from handoff.score import kind
from handoff.trace import parse
from handoff.zetaris import run_sql

TALK_COLS = ("id", "created_at", "speaker", "channel", "content")
ACTION_COLS = ("id", "created_at", "speaker", "action_type", "action", "output", "narration")
AHEAD = re.compile(
    r"\b(i(?:['’]?ll| will| am going to|['’]m going to)|let me|on it|next,? i(?:['’]m| am| will|['’]ll)|"
    r"now i(?:['’]m| am)|i(?:['’]m| am) (?:about to|starting)|will follow|"
    r"(?:will|going to) (?:post|send|ack|add|run|update|write|fix|push|commit|ship|open|report))\b",
    re.I,
)

# Offers that only apply if someone asks are not promises; the model does not always drop them.
CONDITIONAL = re.compile(
    r"\bif (?:requested|asked|needed|wanted|you (?:want|like|prefer)|[\w-]+ (?:requests?|asks?|wants?))\b", re.I
)

TRACE_EXTRACT_SYSTEM = (
    "You read one message from an AI agent's work log: text it wrote while working, or a message it "
    "sent to a person or another agent. List every concrete task the SPEAKER commits to doing "
    "THEMSELVES after this message (I'll, I will, let me, next I'm, now I'm, X will follow): building, "
    "editing, running, checking, sending or posting something. Not commitments: work described as "
    "already done, questions, thanks or agreement, asking someone else to act, ongoing states with "
    "no deliverable (keep monitoring, stay available), and conditional offers that only apply if "
    "someone asks (if requested, if you want, happy to). At most 3, each a separate deliverable. "
    "Reply with JSON only: "
    '{"commitments": [{"task": "short imperative, max 12 words", '
    '"done_when": "what visible action would show it was done, max 15 words"}]} '
    "with an empty list when there are none."
)


def _write(rows: list[dict], cols: tuple[str, ...], path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({c: [str(r.get(c) or "") for r in rows] for c in cols}), path)


def _read(table: str, cols: tuple[str, ...]) -> list[dict]:
    recs = run_sql(f"SELECT {', '.join(cols)} FROM HANDOFF.{table}", limit=20000)
    rows = [dict(zip(cols, rec)) if isinstance(rec, list) else rec for rec in recs]
    return [{c: "" if r.get(c) is None else str(r.get(c)) for c in cols} for r in rows]


def store(trace: dict, name: str) -> dict:
    """Put talk and actions in Zetaris and read them back; fall back to memory if it is down."""
    base = ident(f"trace_{name}_{uuid.uuid4().hex[:6]}")
    tables = {"talk": f"{base}_talk", "actions": f"{base}_actions"}
    try:
        for key, cols in (("talk", TALK_COLS), ("actions", ACTION_COLS)):
            local = data_dir() / "uploads" / f"{tables[key]}.parquet"
            _write(trace[key], cols, local)
            remote = copy_into_driver(local, local.name)
            _sql_ok('CREATE LIGHTNING DATABASE HANDOFF DESCRIBE BY "Handoff swarm investigations"')
            _sql_ok(
                f"CREATE LIGHTNING FILESTORE TABLE {tables[key]} FROM HANDOFF FORMAT PARQUET OPTIONS ("
                f'PATH "{remote}", inferSchema "true")'
            )
        talk, actions = _read(tables["talk"], TALK_COLS), _read(tables["actions"], ACTION_COLS)
    except Exception as e:  # docker or Zetaris not running: grade from memory, and say so
        return {"store": "memory", "why": str(e)[:200], "talk": trace["talk"], "actions": trace["actions"]}
    if len(talk) != len(trace["talk"]) or len(actions) != len(trace["actions"]):
        return {"store": "memory", "why": "Zetaris read back a different row count",
                "talk": trace["talk"], "actions": trace["actions"]}
    return {"store": "zetaris", "tables": [f"HANDOFF.{t}" for t in tables.values()], "talk": talk, "actions": actions}


def candidates(talk: list[dict], actors: set[str]) -> list[dict]:
    """Lines by agents whose actions we have, phrased like something still to do."""
    return [
        r for r in talk
        if r["speaker"] in actors and r.get("channel") != "received"
        and (kind(r["content"]) == "commit" or AHEAD.search(r["content"]))
    ]


def extract_all(row: dict) -> tuple[list[dict], str | None]:
    """Every commitment in one line, as promise rows; a line with two promises yields two."""
    res = chat(
        "extract",
        [
            {"role": "system", "content": TRACE_EXTRACT_SYSTEM},
            {"role": "user", "content": f"Speaker: {row['speaker']}\nMessage: {row['content'][:1500]}"},
        ],
        max_tokens=300,
    )
    parsed = parse_json(res.get("text", "")) if res.get("ok") else None
    items = [
        c for c in (parsed or {}).get("commitments") or []
        if isinstance(c, dict) and c.get("task") and not CONDITIONAL.search(c["task"])
    ][:3]
    base = {
        "source_id": row["id"], "created_at": row["created_at"], "speaker": row["speaker"],
        "slice": row["slice_slug"], "goal_title": row.get("goal_title"), "quote": row["content"][:400],
        "is_commitment": True, "extract_model": res.get("model"), "extract_route": res.get("route"),
        "extract_receipt": res.get("receipt"),
    }
    promises = [
        {**base, "id": row["id"] if len(items) == 1 else f"{row['id']}#{n}",
         "task": c["task"], "done_when": c.get("done_when") or ""}
        for n, c in enumerate(items, 1)
    ]
    return promises, None if res.get("ok") else res.get("error")


def _judge(
    promise: dict, talk: list[dict], actions: list[dict], top: int = 14, max_tokens: int = 2500, first: int = 6
) -> dict:
    at = parse_ts(promise["created_at"])
    own_send = promise["source_id"].split(":msg")[0]
    later = [
        a for a in actions
        if a["speaker"] == promise["speaker"] and a["id"] != own_send
        and at and a["ts"] and at <= a["ts"] <= at + WINDOW
    ]
    chat = [
        {"id": r["id"], "ts": parse_ts(r["created_at"]), "action_type": "chat",
         "action": r["content"][:300], "output": "", "narration": ""}
        for r in talk
        if r["speaker"] == promise["speaker"] and r["id"] != promise["source_id"] and r.get("channel") != "received"
    ]
    chat = [c for c in chat if at and c["ts"] and at < c["ts"] <= at + WINDOW]
    base = {**promise, "turns_in_window": len(later), "chat_in_window": len(chat)}
    window = sorted(later + chat, key=lambda t: t["ts"])
    if not window:
        return {**base, "verdict": "unclear", "turn_ids": [], "judge_model": None, "judge_route": "rule",
                "reason": "The trace ends before this agent does anything after the promise."}
    return judge_window(promise, window, base, top=top, max_tokens=max_tokens, first=first)


def second_look(verdicts: list[dict], promises: list[dict], talk: list[dict], actions: list[dict], workers: int) -> int:
    """Judge every model-made not_done again with 60 actions instead of 14 (the 20 right after the
    promise always among them), as the Village run does.

    A narrow first pass can miss the one action that shows the work. Returns how many changed.
    """
    todo = [(i, p) for i, (p, v) in enumerate(zip(promises, verdicts))
            if v["verdict"] == "not_done" and v.get("judge_route") != "rule"]
    with ThreadPoolExecutor(workers) as pool:
        wide = list(pool.map(lambda ip: _judge(ip[1], talk, actions, top=60, max_tokens=6000, first=20), todo))
    changed = 0
    for (i, _), w in zip(todo, wide):
        if w.get("judge_error") or w["verdict"] == "error":
            verdicts[i]["second_look"] = "failed"
            continue
        changed += w["verdict"] != "not_done"
        verdicts[i] = {**w, "first_verdict": "not_done", "second_look": True}
    return changed


def grade(trace: dict, name: str, max_promises: int = 25, workers: int = 4) -> dict:
    kept = store(trace, name)
    talk, actions = kept["talk"], kept["actions"]
    for a in actions:
        a["ts"] = parse_ts(a["created_at"])
    actors = {a["speaker"] for a in actions}
    cands = candidates(talk, actors)
    rows = [
        {"id": r["id"], "created_at": r["created_at"], "speaker": r["speaker"], "content": r["content"],
         "slice_slug": ident(name), "goal_title": name}
        for r in cands[:max_promises]
    ]
    with ThreadPoolExecutor(workers) as pool:
        extracted = list(pool.map(extract_all, rows))
    # A failed call is not a verdict: retry those lines once, one at a time, before giving up.
    extracted = [extract_all(row) if err else (found, err) for row, (found, err) in zip(rows, extracted)]
    promises = [p for found, _ in extracted for p in found]
    with ThreadPoolExecutor(workers) as pool:
        verdicts = list(pool.map(lambda p: _judge(p, talk, actions), promises))
    verdicts = [_judge(p, talk, actions) if v.get("judge_error") else v for p, v in zip(promises, verdicts)]
    for v in verdicts:
        if v.get("judge_error"):
            v["verdict"] = "error"  # the judge never answered; never scored, never shown as unclear
    changed = second_look(verdicts, promises, talk, actions, workers)
    return {
        "store": {k: v for k, v in kept.items() if k not in ("talk", "actions")},
        "candidates": len(cands),
        "graded_candidates": len(rows),
        "extract_errors": sum(1 for _, err in extracted if err),
        "judge_errors": sum(1 for v in verdicts if v.get("judge_error")),
        "second_looks": sum(1 for v in verdicts if v.get("second_look") is True),
        "second_look_changed": changed,
        "verdicts": verdicts,
        "actions": actions,
        "talk": talk,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path")
    ap.add_argument("--name", default="trace")
    ap.add_argument("--max", type=int, default=25)
    args = ap.parse_args()
    trace = parse(open(args.path, encoding="utf-8").read(), args.name)
    out = grade(trace, args.name, max_promises=args.max)
    print(json.dumps({k: v for k, v in out.items() if k not in ("actions", "talk")}, indent=2, default=str))
    print(f"{len(out['verdicts'])} promises graded from {out['candidates']} candidates", file=sys.stderr)


if __name__ == "__main__":
    main()

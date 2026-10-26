"""Check each chat promise against the promiser's own computer-use turns, read through Zetaris.

1. Promise-like chat lines come from HANDOFF.promises (regex prefilter).
2. Nemotron Lightning decides whether the line commits to a concrete task, and names it.
3. The promiser's executed actions in the next 24 hours come from HANDOFF.cu_turns.
4. Nemotron Super judges them: kept, partial, not_done or unclear, citing turn ids.

Only executed actions and tool output count as evidence. The agent's narration is shown
to the judge as context and can never make a promise "kept" on its own.

    python -m handoff.evidence --limit 30      # a sample first
    python -m handoff.evidence                 # every promise, resumable
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from handoff.fetch import data_dir
from handoff.goals import parse_ts
from handoff.llm import chat, parse_json
from handoff.score import as_rows, kind
from handoff.zetaris import run_sql

WINDOW = timedelta(hours=24)
SKIP_ACTIONS = ("talk", "screenshot", "wait", "send_message_back_to_chat", "get_pixel_coords_of_element")
WORD = re.compile(r"[a-z0-9][a-z0-9._/-]{2,}")
STOP = set("the and for that this with you your will have from into then them they what when just also about".split())

EXTRACT_SYSTEM = (
    "You read one chat message from an AI agent working in a team of agents. Decide whether the "
    "SPEAKER commits to doing a concrete task THEMSELVES in the future (I'll, I will, let me, on it): "
    "sending, building, posting, editing, checking something. Not commitments: asking or telling "
    "another agent to do something, thanks or agreement, status reports, anything described as "
    "already done, and ongoing states with no deliverable (keep monitoring, stay available, maintain "
    "a stance). If the message holds several, pick the speaker's own most concrete one. "
    "Reply with JSON only: "
    '{"is_commitment": bool, "task": "short imperative, max 12 words", '
    '"done_when": "what visible action would show it was done, max 15 words"}'
)

JUDGE_SYSTEM = (
    "You audit whether an AI agent kept a promise, using its own computer-use log. Each turn shows "
    "the executed action, the tool output, and the agent's narration. Only the executed action and "
    "the tool output are evidence. Narration is the agent's own claim and never proves anything by "
    "itself. Lines marked chat are the agent's later chat messages: they count only when the task "
    "itself is to post something in chat and the message contains the deliverable, not a claim that "
    "it was done. Verdicts: kept (an executed action or its output shows the task done), partial (work "
    "clearly started but not finished), not_done (the actions show other work and nothing toward "
    "the task), unclear (cannot tell from these turns, for example the proof would only be on "
    "screen). Reply with JSON only: "
    '{"verdict": "kept|partial|not_done|unclear", "turn_ids": ["id"], "reason": "one sentence"}'
)


def out_dir() -> Path:
    path = data_dir() / "evidence"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _done(path: Path) -> dict[str, dict]:
    rows = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row["id"]] = row
    return rows


_CHAT: dict[tuple[str, str], list[dict]] = {}


def candidates() -> list[dict]:
    rows = as_rows(
        run_sql(
            "SELECT id, created_at, speaker, content, slice_slug, goal_id, goal_title FROM HANDOFF.promises",
            limit=20000,
        )
    )
    for r in rows:
        _CHAT.setdefault((r["slice_slug"], r["speaker"]), []).append(
            {"id": r["id"], "ts": parse_ts(r["created_at"]), "action_type": "chat",
             "action": (r.get("content") or "")[:300], "output": "", "narration": ""}
        )
    return [r for r in rows if kind(r.get("content") or "") == "commit"]


def extract(row: dict) -> dict:
    res = chat(
        "extract",
        [
            {"role": "system", "content": EXTRACT_SYSTEM},
            {"role": "user", "content": f"Speaker: {row['speaker']}\nMessage: {row['content'][:1500]}"},
        ],
        max_tokens=120,
    )
    parsed = parse_json(res.get("text", "")) if res.get("ok") else None
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "speaker": row["speaker"],
        "slice": row["slice_slug"],
        "goal_title": row.get("goal_title"),
        "quote": row["content"][:400],
        "is_commitment": bool(parsed and parsed.get("is_commitment")),
        "task": (parsed or {}).get("task") or "",
        "done_when": (parsed or {}).get("done_when") or "",
        "extract_model": res.get("model"),
        "extract_route": res.get("route"),
        "extract_receipt": res.get("receipt"),
        "extract_error": None if res.get("ok") else res.get("error"),
    }


_TURNS: dict[tuple[str, str], list[dict]] = {}


def turns_for(slice_slug: str, speaker: str) -> list[dict]:
    key = (slice_slug, speaker)
    if key not in _TURNS:
        skip = ", ".join(f"'{a}'" for a in SKIP_ACTIONS)
        who = speaker.replace("'", "''")
        sql = (
            "SELECT id, created_at, action_type, action, output, narration FROM HANDOFF.cu_turns "
            f"WHERE slice_slug = '{slice_slug}' AND speaker = '{who}' AND action_type NOT IN ({skip})"
        )
        rows = []
        for rec in run_sql(sql, limit=60000):
            if isinstance(rec, list) and len(rec) >= 6:
                rows.append(
                    {
                        "id": rec[0],
                        "ts": parse_ts(rec[1]),
                        "created_at": rec[1],
                        "action_type": rec[2],
                        "action": rec[3] or "",
                        "output": rec[4] or "",
                        "narration": rec[5] or "",
                    }
                )
        rows.sort(key=lambda r: r["ts"] or parse_ts("2000-01-01"))
        _TURNS[key] = rows
    return _TURNS[key]


def words(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if w not in STOP}


def rank(promise: dict, turns: list[dict], top: int = 10) -> list[dict]:
    want = words(f"{promise['task']} {promise['done_when']}")
    scored = []
    for t in turns:
        hit = len(want & words(f"{t['action']} {t['output']}")) * 2 + len(want & words(t["narration"]))
        scored.append((hit, t))
    best = [t for hit, t in sorted(scored, key=lambda x: -x[0])[:top] if hit > 0]
    if len(best) < 4:
        best += [t for t in turns[:4] if t not in best]
    return sorted(best[:top], key=lambda t: t["ts"])


def judge(promise: dict) -> dict:
    at = parse_ts(promise["created_at"])
    window = [t for t in turns_for(promise["slice"], promise["speaker"]) if at and t["ts"] and at <= t["ts"] <= at + WINDOW]
    later_chat = [
        m for m in _CHAT.get((promise["slice"], promise["speaker"]), [])
        if at and m["ts"] and at < m["ts"] <= at + WINDOW and m["id"] != promise["id"]
    ]
    base = {**promise, "turns_in_window": len(window), "chat_in_window": len(later_chat)}
    window = sorted(window + later_chat, key=lambda t: t["ts"])
    if not window:
        return {**base, "verdict": "not_done", "turn_ids": [], "judge_model": None, "judge_route": "rule",
                "reason": "No computer action or chat message by this agent in the 24 hours after the promise."}
    return judge_window(promise, window, base)


def judge_window(promise: dict, window: list[dict], base: dict, top: int = 14, max_tokens: int = 2500) -> dict:
    """Ask the judge for a verdict on one promise, given the agent's later turns (actions and chat)."""
    at = parse_ts(promise["created_at"])
    shown = rank(promise, window, top=top)
    lines = []
    for t in shown:
        mins = int((t["ts"] - at).total_seconds() // 60)
        lines.append(
            f"[{t['id']}] +{mins}min {t['action_type']}: {t['action'][:220]}"
            f" | output: {t['output'][:160]} | narration: {t['narration'][:160]}"
        )
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Agent: {promise['speaker']}\nPromise (chat): {promise['quote'][:300]}\n"
                f"Task: {promise['task']}\nDone when: {promise['done_when']}\n"
                f"{base['turns_in_window']} executed turns and {base['chat_in_window']} chat messages "
                f"in the next 24 hours; the most relevant {len(shown)}:\n"
                + "\n".join(lines)
            ),
        },
    ]
    for _ in range(2):  # long reasoning sometimes leaves an empty answer; ask once more
        res = chat("judge", messages, max_tokens=max_tokens)
        parsed = parse_json(res.get("text", "")) if res.get("ok") else None
        if parsed or not res.get("ok"):
            break
    verdict = (parsed or {}).get("verdict")
    if verdict not in ("kept", "partial", "not_done", "unclear"):
        verdict = "unclear"
    known = {t["id"] for t in shown}
    cited = [i for i in (parsed or {}).get("turn_ids") or [] if i in known]
    return {
        **base,
        "verdict": verdict,
        "turn_ids": cited,
        "reason": (parsed or {}).get("reason") or (res.get("error") or "Judge reply was not JSON."),
        "judge_model": res.get("model"),
        "judge_route": res.get("route"),
        "judge_receipt": res.get("receipt"),
        "judge_error": None if res.get("ok") else res.get("error"),
    }


def _append(path: Path, rows: list[dict]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def run(limit: int | None, workers: int) -> dict:
    ex_path, ju_path = out_dir() / "extract.jsonl", out_dir() / "judged.jsonl"
    cands = candidates()
    if limit:
        cands = cands[:limit]
    print(f"{len(cands)} promise-like lines from Zetaris", file=sys.stderr)

    have = _done(ex_path)
    todo = [c for c in cands if c["id"] not in have or have[c["id"]].get("extract_error")]  # retry failures
    with ThreadPoolExecutor(workers) as pool:
        for i, row in enumerate(pool.map(extract, todo), 1):
            _append(ex_path, [row])
            have[row["id"]] = row
            if i % 100 == 0:
                print(f"  extracted {i}/{len(todo)}", file=sys.stderr, flush=True)
    promises = [have[c["id"]] for c in cands if have[c["id"]].get("is_commitment")]
    print(f"{len(promises)} are concrete commitments", file=sys.stderr)

    # Check ownership before judging, so no judge call is spent on another agent's task.
    run_owner_check(workers, promises)
    owner = _done(out_dir() / "owner.jsonl")
    promises = [p for p in promises if owner.get(p["id"], {}).get("owns") is not False]
    print(f"{len(promises)} are the speaker's own", file=sys.stderr, flush=True)

    for p in promises:  # warm the per-agent turn cache serially; Zetaris calls are heavy
        turns_for(p["slice"], p["speaker"])
    judged = _done(ju_path)
    todo = [p for p in promises if p["id"] not in judged or judged[p["id"]].get("judge_error")]
    with ThreadPoolExecutor(workers) as pool:
        for i, row in enumerate(pool.map(judge, todo), 1):
            _append(ju_path, [row])
            judged[row["id"]] = row
            if i % 50 == 0:
                print(f"  judged {i}/{len(todo)}", file=sys.stderr, flush=True)
    final = [judged[p["id"]] for p in promises]
    return summarize(final)


OWNER_SYSTEM = (
    "You check one extraction. Given a chat message from an AI agent and a task taken from it, "
    "answer whether the SPEAKER said they themselves will do that task. If the message asks, "
    "thanks or tells another agent to do it, the answer is no. Reply with JSON only: "
    '{"speaker_owns_task": bool}'
)


def owner_check(row: dict) -> dict:
    # Ownership needs reasoning: messages often mix a request to another agent with the
    # speaker's own follow-up ("after your push I'll verify"). Lightning without thinking
    # dropped clear first-person promises, so this uses the judge model.
    msgs = [
        {"role": "system", "content": OWNER_SYSTEM},
        {"role": "user", "content": f"Speaker: {row['speaker']}\nMessage: {row['quote']}\nTask: {row['task']}"},
    ]
    parsed = None
    for _ in range(2):
        res = chat("judge", msgs, max_tokens=1500)
        parsed = parse_json(res.get("text", "")) if res.get("ok") else None
        if parsed:
            break
    owns = None if parsed is None else bool(parsed.get("speaker_owns_task"))
    return {"id": row["id"], "owns": owns, "model": res.get("model"), "receipt": res.get("receipt")}


def run_owner_check(workers: int = 8, rows: list[dict] | None = None) -> dict:
    """Mark extractions whose task belonged to another agent (a request, not a promise)."""
    path = out_dir() / "owner.jsonl"
    done = _done(path)
    if rows is None:
        rows = list(_done(out_dir() / "judged.jsonl").values())
    todo = [r for r in rows if r["id"] not in done or done[r["id"]].get("owns") is None]
    with ThreadPoolExecutor(workers) as pool:
        for i, row in enumerate(pool.map(owner_check, todo), 1):
            _append(path, [row])
            if i % 100 == 0:
                print(f"  owner-checked {i}/{len(todo)}", file=sys.stderr, flush=True)
    rows = _done(path).values()
    return {"checked": len(rows), "not_speakers_task": sum(1 for r in rows if r["owns"] is False),
            "unparsed": sum(1 for r in rows if r["owns"] is None)}


def apply_owner_check(final: list[dict]) -> list[dict]:
    path = out_dir() / "owner.jsonl"
    if not path.is_file():
        return final
    wrong = {k for k, v in _done(path).items() if v.get("owns") is False}
    return [r for r in final if r["id"] not in wrong]


def apply_second_look(final: list[dict]) -> list[dict]:
    """Every not_done verdict was judged again with a wider view; that verdict is final."""
    path = out_dir() / "second.jsonl"
    if not path.is_file():
        return final
    second = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("reason"):  # an empty reply keeps the first verdict
                second[row["id"]] = row
    out = []
    for r in final:
        s = second.get(r["id"])
        # Only a not_done first verdict gets a second look; a re-judged first verdict that is no
        # longer not_done must not be overridden by an older second look.
        if s and r["verdict"] == "not_done" and s.get("second") in ("kept", "partial", "not_done", "unclear"):
            r = {**r, "first_verdict": r["verdict"], "verdict": s["second"], "reason": s["reason"],
                 "turn_ids": s.get("turn_ids") or [], "second_look": True,
                 "judge_model": s.get("model") or r.get("judge_model"), "judge_receipt": s.get("receipt"),
                 "judge_route": "meterless" if (s.get("receipt") or {}).get("receipt_id") else "nebius-fallback"}
        out.append(r)
    for r in out:
        receipt = r.get("judge_receipt") or {}
        r["receipt_id"] = receipt.get("receipt_id")
        r["judge_ms"] = receipt.get("ms")
    return out


def summarize(final: list[dict]) -> dict:
    before = len(final)
    final = apply_second_look(apply_owner_check(final))
    counts = Counter(r["verdict"] for r in final)
    by_slice: dict[str, Counter] = {}
    for r in final:
        by_slice.setdefault(r["slice"], Counter())[r["verdict"]] += 1
    summary = {
        "promises": len(final),
        "dropped_not_speakers_task": before - len(final),
        "counts": dict(counts),
        "judge_routes": dict(Counter(str(r.get("judge_route")) for r in final)),
        "extract_routes": dict(Counter(str(r.get("extract_route")) for r in final)),
        "second_look": {
            "checked": sum(1 for r in final if r.get("second_look")),
            "changed": sum(1 for r in final if r.get("second_look") and r["verdict"] != r["first_verdict"]),
        },
        "weeks": {k: dict(v) for k, v in by_slice.items()},
        "rule": "Only executed actions and tool output count; narration never proves a promise.",
    }
    (data_dir() / "evidence_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    table = [
        {k: str(r.get(k) if not isinstance(r.get(k), list) else json.dumps(r.get(k))) for k in COLUMNS}
        for r in final
    ]
    (data_dir() / "slices").mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(table), data_dir() / "slices" / "verdicts.parquet", compression="zstd")
    return summary


COLUMNS = (
    "id", "created_at", "speaker", "slice", "goal_title", "quote", "task", "done_when", "verdict",
    "reason", "turn_ids", "turns_in_window", "chat_in_window", "judge_model", "judge_route", "extract_model",
    "first_verdict", "second_look", "receipt_id", "judge_ms",
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--summarize", action="store_true", help="rebuild the summary and Parquet from saved verdicts")
    ap.add_argument("--owner-check", action="store_true", help="drop verdicts whose task was another agent's")
    args = ap.parse_args()
    if args.owner_check:
        print(json.dumps(run_owner_check(args.workers), indent=2))
        return
    if args.summarize:
        # Latest row per promise: a re-judge appends, so earlier rows for the same id are superseded.
        judged = list(_done(out_dir() / "judged.jsonl").values())
        print(json.dumps(summarize(judged), indent=2))
        return
    print(json.dumps(run(args.limit, args.workers), indent=2))


if __name__ == "__main__":
    main()

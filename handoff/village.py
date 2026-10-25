"""The Village investigation on the desk: evidence verdicts read back through Zetaris.

    python -m handoff.village publish     # copy verdicts.parquet in and (re)register HANDOFF.verdicts
    python -m handoff.village remember    # store every verdict in H-MEM with its provenance
    python -m handoff.village why         # one cited Nemotron paragraph, cached in data/why.json
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter

from handoff.fetch import data_dir
from handoff.hmem import health as hmem_health
from handoff.hmem import recall, remember_verdict, _index, _save_index
from handoff.llm import chat
from handoff.register import CONTAINER, REMOTE_DIR
from handoff.zetaris import run_sql

TABLE = "HANDOFF.verdicts"
COLS = ("id", "created_at", "speaker", "slice", "goal_title", "quote", "task", "verdict", "reason", "turn_ids",
        "turns_in_window", "chat_in_window", "judge_model", "judge_route")
VERDICTS = ("kept", "partial", "not_done", "unclear")

WHY_SYSTEM = (
    "You explain why a team of AI agents let work slip, using only the JSON you are given: verdict "
    "counts, per-agent rates, and example cases with ids. Each verdict was judged against the "
    "agent's own executed computer actions, not its words. Write 4 or 5 plain sentences: the "
    "headline number, which agents left the most promises undone, the common pattern in the "
    "reasons, and one concrete change for the next session. Each item is a promise the agent made "
    "itself, never an assigned task. Put the promise id in square brackets after every claim about "
    "a specific case, like [3f2a…]. Use only ids from the JSON. Do not invent facts."
)


def publish() -> None:
    src = data_dir() / "slices" / "verdicts.parquet"
    subprocess.run(["docker", "cp", str(src), f"{CONTAINER}:{REMOTE_DIR}/verdicts.parquet"], check=True)
    try:
        run_sql(f"DROP LIGHTNING DATABASE TABLE {TABLE}", limit=5)
    except RuntimeError as e:
        print(f"skip drop: {str(e)[:120]}", file=sys.stderr)
    run_sql(
        'CREATE LIGHTNING FILESTORE TABLE verdicts FROM HANDOFF FORMAT PARQUET OPTIONS '
        f'(PATH "{REMOTE_DIR}/verdicts.parquet", inferSchema "true")',
        limit=5,
    )
    print(run_sql(f"SELECT verdict, count(*) FROM {TABLE} GROUP BY verdict", limit=10))


def rows() -> list[dict]:
    out = []
    for rec in run_sql(f"SELECT {', '.join(COLS)} FROM {TABLE}", limit=20000):
        if isinstance(rec, list):
            row = dict(zip(COLS, rec))
            row["turn_ids"] = json.loads(row.get("turn_ids") or "[]")
            out.append(row)
    return out


def per_agent() -> list[dict]:
    sql = (
        f"SELECT speaker, verdict, count(*) AS n FROM {TABLE} GROUP BY speaker, verdict"
    )
    agents: dict[str, Counter] = {}
    for rec in run_sql(sql, limit=500):
        agents.setdefault(rec[0], Counter())[rec[1]] = int(rec[2])
    table = []
    for name, c in agents.items():
        total = sum(c.values())
        table.append(
            {
                "agent": name,
                "promises": total,
                **{v: c[v] for v in VERDICTS},
                "undone_rate": round((c["not_done"] + c["partial"]) / total, 2) if total else 0,
            }
        )
    return sorted(table, key=lambda r: (-r["not_done"], -r["promises"]))


def cited_turns(ids: list[str]) -> list[dict]:
    safe = [i for i in ids if i and all(ch.isalnum() or ch == "-" for ch in i)][:20]
    if not safe:
        return []
    inlist = ", ".join(f"'{i}'" for i in safe)
    out = []
    for rec in run_sql(
        f"SELECT id, created_at, action_type, action, output FROM HANDOFF.cu_turns WHERE id IN ({inlist})", limit=40
    ):
        out.append(dict(zip(("id", "created_at", "action_type", "action", "output"), rec)))
    for rec in run_sql(f"SELECT id, created_at, content FROM HANDOFF.promises WHERE id IN ({inlist})", limit=40):
        out.append({"id": rec[0], "created_at": rec[1], "action_type": "chat", "action": (rec[2] or "")[:600], "output": ""})
    return sorted(out, key=lambda r: str(r.get("created_at")))


def remember_all() -> int:
    if not hmem_health().get("ok"):
        raise SystemExit("H-MEM helper is not running: cd hmem && npm run serve")
    index = _index()
    n = 0
    for row in rows():
        if remember_verdict(row, index):
            n += 1
    _save_index(index)
    return n


def why(force: bool = False) -> dict:
    cache = data_dir() / "why.json"
    all_rows = rows()
    counts = Counter(r["verdict"] for r in all_rows)
    if cache.is_file() and not force:
        cached = json.loads(cache.read_text(encoding="utf-8"))
        if cached.get("counts") == dict(counts):
            return cached
    agents = per_agent()[:8]
    undone = [r for r in all_rows if r["verdict"] in ("not_done", "partial")]
    examples = [
        {"id": r["id"][:8], "agent": r["speaker"], "verdict": r["verdict"], "task": r["task"], "reason": r["reason"][:200]}
        for r in undone[:: max(1, len(undone) // 14)][:14]
    ]
    payload = {"promises": len(all_rows), "counts": dict(counts), "agents": agents, "examples": examples}
    res = chat("why", [{"role": "system", "content": WHY_SYSTEM}, {"role": "user", "content": json.dumps(payload)}], max_tokens=2500)
    out = {
        "ok": bool(res.get("ok") and res.get("text")),
        "why": res.get("text") or "",
        "model": res.get("model"),
        "route": res.get("route"),
        "promises": len(all_rows),
        "counts": dict(counts),
        "cited_ids": [e["id"] for e in examples],
        "error": res.get("error"),
    }
    if out["ok"]:
        cache.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def investigation() -> dict:
    all_rows = rows()
    counts = Counter(r["verdict"] for r in all_rows)
    weeks = {}
    for r in all_rows:
        w = weeks.setdefault(r["slice"], {"title": r["goal_title"], "counts": Counter()})
        w["counts"][r["verdict"]] += 1
    order = {"not_done": 0, "partial": 1, "unclear": 2, "kept": 3}
    verdicts = sorted(all_rows, key=lambda r: (order.get(r["verdict"], 9), str(r["created_at"])))
    return {
        "name": "AI Village, three weeks",
        "source": f"{TABLE} + HANDOFF.cu_turns + HANDOFF.promises",
        "engine": "zetaris",
        "evidence": True,
        "promises": len(all_rows),
        "counts": {v: counts[v] for v in VERDICTS},
        "weeks": [
            {"slug": k, "title": w["title"], "open": w["counts"]["not_done"] + w["counts"]["partial"], "counts": dict(w["counts"])}
            for k, w in weeks.items()
        ],
        "agents": per_agent(),
        "verdicts": [
            {
                "id": r["id"],
                "verdict": r["verdict"],
                "from": r["speaker"],
                "slice": r["slice"],
                "at": r["created_at"],
                "quote": r["quote"],
                "task": r["task"],
                "why": r["reason"],
                "turn_ids": r["turn_ids"],
                "turns_in_window": r["turns_in_window"],
                "judge_model": r["judge_model"],
            }
            for r in verdicts
        ],
        "memory": recall("AI Village", query="promises not done partial dropped"),
        "nemotron": why(),
        "for_sale": False,
        "task_blocked": "Village data is research-only. Handoff will not build a listed task from it.",
    }


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "publish"
    if cmd == "publish":
        publish()
    elif cmd == "remember":
        print(f"stored {remember_all()} verdicts in H-MEM")
    elif cmd == "why":
        print(json.dumps(why(force=True), indent=2))
    else:
        raise SystemExit("usage: python -m handoff.village [publish|remember|why]")


if __name__ == "__main__":
    main()

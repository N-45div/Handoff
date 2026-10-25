"""Estimate how often a not_done verdict was really missed evidence.

The judge sees the 14 turns that best match the task. A fixed random sample of not_done
verdicts is judged again with a much wider view: the 40 best matches plus everything in the
first three hours after the promise. Flips to kept or partial are counted as misses.

    python -m handoff.second_look --n 60
"""

from __future__ import annotations

import argparse
import json
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from handoff.evidence import JUDGE_SYSTEM, WINDOW, _CHAT, candidates, rank, turns_for
from handoff.fetch import data_dir
from handoff.goals import parse_ts
from handoff.llm import chat, parse_json


def wide_judge(p: dict) -> dict:
    at = parse_ts(p["created_at"])
    window = [t for t in turns_for(p["slice"], p["speaker"]) if at and t["ts"] and at <= t["ts"] <= at + WINDOW]
    window += [m for m in _CHAT.get((p["slice"], p["speaker"]), []) if at and m["ts"] and at < m["ts"] <= at + WINDOW]
    early = [t for t in window if t["ts"] <= at + timedelta(hours=3)][:30]
    shown = {t["id"]: t for t in rank(p, window, top=40) + early}
    lines = [
        f"[{t['id']}] +{int((t['ts'] - at).total_seconds() // 60)}min {t['action_type']}: {t['action'][:200]}"
        f" | output: {t['output'][:120]} | narration: {t['narration'][:100]}"
        for t in sorted(shown.values(), key=lambda t: t["ts"])[:60]
    ]
    msg = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": f"Agent: {p['speaker']}\nPromise (chat): {p['quote'][:300]}\nTask: {p['task']}\n"
                                    f"Done when: {p['done_when']}\n{len(lines)} turns from the next 24 hours:\n" + "\n".join(lines)},
    ]
    parsed = None
    for _ in range(2):
        res = chat("judge", msg, max_tokens=6000)
        parsed = parse_json(res.get("text", "")) if res.get("ok") else None
        if parsed:
            break
    known = set(shown)
    return {"id": p["id"], "first": p["verdict"], "second": (parsed or {}).get("verdict") or "unclear",
            "reason": (parsed or {}).get("reason") or "", "shown": len(lines),
            "turn_ids": [i for i in (parsed or {}).get("turn_ids") or [] if i in known],
            "model": res.get("model"), "receipt": res.get("receipt")}


def run_all(workers: int = 6) -> None:
    """Second look for every model-judged not_done verdict. Resumable; feeds the final verdicts."""
    candidates()
    path = data_dir() / "evidence" / "second.jsonl"
    done = {json.loads(l)["id"] for l in path.read_text(encoding="utf-8").splitlines() if l.strip()} if path.is_file() else set()
    judged = [json.loads(l) for l in (data_dir() / "evidence" / "judged.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    todo = [r for r in judged if r["verdict"] == "not_done" and r.get("judge_route") != "rule" and r["id"] not in done]
    for p in todo:
        turns_for(p["slice"], p["speaker"])
    with ThreadPoolExecutor(workers) as ex, path.open("a", encoding="utf-8") as fh:
        for i, row in enumerate(ex.map(wide_judge, todo), 1):
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            if i % 50 == 0:
                print(f"  second look {i}/{len(todo)}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--all", action="store_true", help="second look for every not_done verdict")
    args = ap.parse_args()
    if args.all:
        run_all()
        return
    candidates()  # fills the chat cache
    judged = [json.loads(l) for l in (data_dir() / "evidence" / "judged.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    pool = [r for r in judged if r["verdict"] == "not_done" and r.get("judge_route") != "rule"]
    sample = random.Random(25).sample(pool, min(args.n, len(pool)))
    for p in sample:
        turns_for(p["slice"], p["speaker"])
    with ThreadPoolExecutor(6) as ex:
        out = list(ex.map(wide_judge, sample))
    flips = [r for r in out if r["second"] in ("kept", "partial")]
    summary = {
        "sampled_not_done": len(out),
        "still_not_done": sum(1 for r in out if r["second"] == "not_done"),
        "flipped_to_kept": sum(1 for r in out if r["second"] == "kept"),
        "flipped_to_partial": sum(1 for r in out if r["second"] == "partial"),
        "now_unclear": sum(1 for r in out if r["second"] == "unclear"),
        "miss_rate": round(len(flips) / len(out), 3) if out else None,
        "method": "Fixed random sample (seed 25) of not_done verdicts, re-judged by the same model with up to 60 turns instead of 14.",
        "rows": out,
    }
    (data_dir() / "second_look.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()

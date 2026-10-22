"""Rank village-wide goals by agent-to-agent handoff density. Today's go/no-go."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from handoff.fetch import CATALOG, data_dir, download, read_jsonl_gz
from handoff.patterns import looks_like_handoff


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:26], fmt)
        except ValueError:
            continue
    return None


def load_goals(raw: Path):
    path = raw / "village_goals.jsonl.gz"
    if not path.exists():
        path = download("village_goals.jsonl.gz")
    return list(read_jsonl_gz(path))


def rank() -> list[dict]:
    raw = data_dir() / "raw"
    goals = load_goals(raw)
    goals.sort(key=lambda g: parse_ts(g.get("start_time")) or datetime.min)

    chat_path = raw / "chat_messages.jsonl.gz"
    if not chat_path.exists():
        print("chat_messages.jsonl.gz missing — ranking goals by schedule only", file=sys.stderr)
        print("run: python -m handoff.fetch catalog   then download chat when ready", file=sys.stderr)
        rows = []
        for g in goals:
            start = parse_ts(g.get("start_time"))
            rows.append(
                {
                    "id": g.get("id"),
                    "goal": (g.get("goal") or "")[:160],
                    "start": g.get("start_time"),
                    "end": g.get("end_time"),
                    "agent_messages": 0,
                    "handoff_like": 0,
                    "density": 0.0,
                    "post_charity": bool(start and start.date().isoformat() >= "2026-04-28"),
                }
            )
        return rows

    buckets = defaultdict(lambda: {"agent_messages": 0, "handoff_like": 0})
    intervals = []
    for g in goals:
        intervals.append(
            (
                parse_ts(g.get("start_time")) or datetime.min,
                parse_ts(g.get("end_time")) or datetime.max,
                g.get("id"),
            )
        )

    for msg in read_jsonl_gz(chat_path):
        if msg.get("speaker_type") != "agent":
            continue
        ts = parse_ts(msg.get("created_at"))
        if ts is None:
            continue
        gid = None
        for start, end, ident in intervals:
            if start <= ts <= end:
                gid = ident
                break
        if gid is None:
            continue
        buckets[gid]["agent_messages"] += 1
        if looks_like_handoff(msg.get("content") or ""):
            buckets[gid]["handoff_like"] += 1

    rows = []
    for g in goals:
        stats = buckets[g.get("id")]
        n = stats["agent_messages"]
        h = stats["handoff_like"]
        start = parse_ts(g.get("start_time"))
        rows.append(
            {
                "id": g.get("id"),
                "goal": (g.get("goal") or "")[:160],
                "start": g.get("start_time"),
                "end": g.get("end_time"),
                "agent_messages": n,
                "handoff_like": h,
                "density": round(h / n, 4) if n else 0.0,
                "post_charity": bool(start and start.date().isoformat() >= "2026-04-28"),
            }
        )
    rows.sort(key=lambda r: (r["post_charity"], r["handoff_like"], r["density"]), reverse=True)
    return rows


def main() -> None:
    for name in CATALOG:
        dest = data_dir() / "raw" / name
        if not dest.exists():
            download(name)
    rows = rank()
    out = data_dir() / "goal_rank.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {out} ({len(rows)} goals)")
    print(f"{'handoffs':>9} {'msgs':>7}  {'post':>4}  start                 goal")
    for r in rows[:12]:
        flag = "yes" if r["post_charity"] else "no"
        print(f"{r['handoff_like']:9d} {r['agent_messages']:7d}  {flag:>4}  {str(r['start'])[:19]:<19}  {r['goal']}")


if __name__ == "__main__":
    main()

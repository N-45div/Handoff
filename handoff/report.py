"""Explain why each week stalled, from Zetaris-scored promises. No Village dump."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from handoff.fetch import data_dir
from handoff.goals import SLICES

WHY = {
    "dropped": "Someone promised in chat and never followed up in that window.",
    "unclaimed": "Someone asked another agent to take it; nobody accepted.",
    "duplicate": "The same agent restated a promise already on the table.",
    "kept": "A later chat line from the same (or answering) agent showed movement.",
}


def load() -> dict:
    path = data_dir() / "verdicts.json"
    if not path.is_file():
        raise SystemExit("missing data/verdicts.json — run python -m handoff.investigate")
    return json.loads(path.read_text(encoding="utf-8"))


def clip(text: str, n: int = 140) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def main() -> None:
    blob = load()
    counts = blob.get("counts") or {}
    print("Handoff v0 — chat-only (computer-use not scored yet)")
    print("Query engine: Zetaris Lightning REST → HANDOFF.promises")
    print("Prior work: Alibi audits past claims. This scores promises between agents.")
    print()
    print(
        f"promises {blob.get('promises')}  "
        f"kept {counts.get('kept', 0)}  "
        f"dropped {counts.get('dropped', 0)}  "
        f"unclaimed {counts.get('unclaimed', 0)}  "
        f"duplicate {counts.get('duplicate', 0)}"
    )
    print()

    by_slice: dict[str, list] = defaultdict(list)
    for v in blob.get("verdicts") or []:
        by_slice[v.get("slice") or "unknown"].append(v)

    titles = {s["slug"]: s["title"] for s in SLICES}
    stall_rank = []
    for slug, title in titles.items():
        items = by_slice.get(slug, [])
        c = Counter(x.get("verdict") for x in items)
        open_n = c["dropped"] + c["unclaimed"]
        stall_rank.append((open_n, slug, title, c, items))
    stall_rank.sort(reverse=True)

    print("Why the swarm stalled (open promises = dropped + unclaimed)")
    for open_n, slug, title, c, items in stall_rank:
        print(f"\n## {title}")
        print(
            f"   kept {c['kept']}  dropped {c['dropped']}  "
            f"unclaimed {c['unclaimed']}  duplicate {c['duplicate']}"
        )
        if open_n == 0:
            print("   no open promises in chat for this window")
            continue
        print(f"   stall: {open_n} open promises")
        dropped = [x for x in items if x.get("verdict") == "dropped"][:2]
        unclaimed = [x for x in items if x.get("verdict") == "unclaimed"][:2]
        for x in dropped:
            print(f"   dropped  {x.get('from')}: {clip(x.get('quote') or '')}")
            print(f"            → {WHY['dropped']}")
        for x in unclaimed:
            print(f"   unclaimed  {x.get('from')}: {clip(x.get('quote') or '')}")
            print(f"              → {WHY['unclaimed']}")

    out = data_dir() / "stall_summary.json"
    summary = {
        "engine": "zetaris",
        "table": blob.get("source"),
        "chat_only": True,
        "counts": counts,
        "weeks": [
            {
                "slug": slug,
                "title": title,
                "open": open_n,
                "counts": dict(c),
            }
            for open_n, slug, title, c, _ in stall_rank
        ],
    }
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()

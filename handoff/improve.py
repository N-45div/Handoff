"""What to change next session, from scored promises. Not a vibe summary."""

from __future__ import annotations

from collections import Counter

TIPS = {
    "dropped": "Do not leave a commit without a later turn from the same agent in that window.",
    "unclaimed": "A request needs an accept in-thread (or an explicit decline) within a few hours.",
    "duplicate": "Restating the same commit is noise; point at the open promise instead.",
}


def suggestions(verdicts: list[dict], limit: int = 8) -> list[dict]:
    ranked = [v for v in verdicts if v.get("verdict") in TIPS]
    ranked.sort(key=lambda v: {"dropped": 0, "unclaimed": 1, "duplicate": 2}.get(v.get("verdict"), 9))
    out = []
    seen = set()
    for v in ranked:
        key = (v.get("verdict"), (v.get("from") or "").lower(), (v.get("quote") or "")[:80])
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "verdict": v.get("verdict"),
                "from": v.get("from"),
                "quote": v.get("quote"),
                "change": TIPS[v["verdict"]],
            }
        )
        if len(out) >= limit:
            break
    return out


def pack_improve(blob: dict) -> dict:
    verdicts = blob.get("verdicts") or []
    counts = Counter(v.get("verdict") for v in verdicts)
    blob["improve"] = suggestions(verdicts)
    blob["improve_summary"] = {
        "dropped": counts["dropped"],
        "unclaimed": counts["unclaimed"],
        "duplicate": counts["duplicate"],
    }
    return blob

"""Score agent-to-agent promises. Works for any swarm table, not just Village."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from handoff.goals import parse_ts
from handoff.patterns import ACCEPT_RE, COMMIT_RE, REQUEST_RE
from handoff.zetaris import run_sql

WHY = {
    "dropped": "Someone promised in chat and never followed up in that window.",
    "unclaimed": "Someone asked another agent to take it; nobody accepted.",
    "duplicate": "The same agent restated a promise already on the table.",
    "kept": "A later chat line from the same (or answering) agent showed movement.",
}


def kind(text: str) -> str | None:
    if not text:
        return None
    if COMMIT_RE.search(text) or ACCEPT_RE.search(text):
        return "commit"
    if REQUEST_RE.search(text):
        return "request"
    return None


def similar(a: str, b: str) -> bool:
    aa = {w for w in a.lower().split() if len(w) > 3}
    bb = {w for w in b.lower().split() if len(w) > 3}
    if not aa or not bb:
        return False
    return len(aa & bb) / min(len(aa), len(bb)) >= 0.45


def as_rows(raw: list) -> list[dict]:
    rows = []
    for rec in raw:
        if isinstance(rec, dict):
            rows.append(rec)
        elif isinstance(rec, list) and len(rec) >= 7:
            rows.append(
                {
                    "id": rec[0],
                    "created_at": rec[1],
                    "speaker": rec[2],
                    "content": rec[3],
                    "slice_slug": rec[4],
                    "goal_id": rec[5],
                    "goal_title": rec[6],
                }
            )
        elif isinstance(rec, list) and len(rec) >= 4:
            rows.append(
                {
                    "id": rec[0],
                    "created_at": rec[1],
                    "speaker": rec[2],
                    "content": rec[3],
                    "slice_slug": rec[4] if len(rec) > 4 else "swarm",
                    "goal_id": rec[5] if len(rec) > 5 else "",
                    "goal_title": rec[6] if len(rec) > 6 else "",
                }
            )
    return rows


def fetch_rows(table: str, limit: int = 20000) -> list[dict]:
    sql = (
        f"SELECT id, created_at, speaker, content, slice_slug, goal_id, goal_title "
        f"FROM {table} LIMIT {int(limit)}"
    )
    return as_rows(run_sql(sql, limit=limit))


def _later_message(rows: list[dict], speaker: str, ts: datetime | None) -> dict | None:
    for row in rows:
        if row.get("speaker") != speaker:
            continue
        other = parse_ts(row.get("created_at"))
        if ts and other and other > ts:
            return row
    return None


def score(rows: list[dict]) -> list[dict]:
    dated = [{**row, "ts": parse_ts(row.get("created_at"))} for row in rows]
    dated.sort(key=lambda e: e["ts"] or datetime.min)

    events = []
    for row in dated:
        k = kind(row.get("content") or "")
        if k:
            events.append({**row, "kind": k})

    by_slice: dict[str, list] = defaultdict(list)
    all_by_slice: dict[str, list] = defaultdict(list)
    for row in dated:
        slug = str(row.get("slice_slug") or row.get("goal_title") or "swarm")
        all_by_slice[slug].append(row)
    for e in events:
        by_slice[str(e.get("slice_slug") or e.get("goal_title") or "swarm")].append(e)

    verdicts = []
    for slug, group in by_slice.items():
        pool = all_by_slice.get(slug, dated)
        for i, e in enumerate(group):
            if e["kind"] == "request":
                partner = None
                for later in group[i + 1 :]:
                    if later.get("speaker") == e.get("speaker"):
                        continue
                    if ACCEPT_RE.search(later.get("content") or ""):
                        if later["ts"] and e["ts"] and later["ts"] - e["ts"] <= timedelta(hours=6):
                            partner = later
                            break
                verdicts.append(_verdict("kept" if partner else "unclaimed", e, slug, partner))
                continue

            dup = None
            for earlier in group[:i]:
                if earlier["kind"] != "commit":
                    continue
                if earlier.get("speaker") == e.get("speaker") and similar(
                    earlier.get("content") or "", e.get("content") or ""
                ):
                    dup = earlier
                    break
            if dup:
                verdicts.append(_verdict("duplicate", e, slug, dup))
                continue

            follow = _later_message(pool, e.get("speaker") or "", e.get("ts"))
            verdicts.append(_verdict("kept" if follow else "dropped", e, slug, follow))
    return verdicts


def _verdict(label: str, e: dict, slug: str, evidence: dict | None) -> dict:
    return {
        "verdict": label,
        "kind": e.get("kind"),
        "why": WHY[label],
        "slice": slug,
        "goal_id": e.get("goal_id"),
        "goal_title": e.get("goal_title") or slug,
        "from": e.get("speaker") or "unknown",
        "to": evidence.get("speaker") if evidence and label in ("kept", "unclaimed") else None,
        "at": e.get("created_at"),
        "quote": (e.get("content") or "")[:280],
        "evidence": evidence.get("id") if evidence else None,
    }


def pack(table: str, rows: list[dict], verdicts: list[dict], name: str) -> dict:
    counts = Counter(v["verdict"] for v in verdicts)
    by_slice: dict[str, Counter] = defaultdict(Counter)
    titles = {}
    for v in verdicts:
        slug = v.get("slice") or "swarm"
        by_slice[slug][v["verdict"]] += 1
        titles[slug] = v.get("goal_title") or slug
    weeks = []
    for slug, c in by_slice.items():
        open_n = c["dropped"] + c["unclaimed"]
        weeks.append(
            {
                "slug": slug,
                "title": titles[slug],
                "open": open_n,
                "counts": {
                    "kept": c["kept"],
                    "dropped": c["dropped"],
                    "unclaimed": c["unclaimed"],
                    "duplicate": c["duplicate"],
                },
            }
        )
    weeks.sort(key=lambda w: w["open"], reverse=True)
    return {
        "name": name,
        "source": table,
        "engine": "zetaris",
        "prior_work": "Alibi is prior work (past-claims audit). Handoff scores promises between agents.",
        "chat_only": True,
        "rows": len(rows),
        "promises": len(verdicts),
        "counts": {
            "kept": counts["kept"],
            "dropped": counts["dropped"],
            "unclaimed": counts["unclaimed"],
            "duplicate": counts["duplicate"],
        },
        "weeks": weeks,
        "verdicts": verdicts,
    }


def investigate_table(table: str, name: str) -> dict:
    rows = fetch_rows(table)
    return pack(table, rows, score(rows), name)

"""Score agent-to-agent promises. Works for any swarm table, not just Village."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from handoff.goals import SLICES, parse_ts

KNOWN_SLUGS = {s["slug"] for s in SLICES}
KNOWN_TITLES = {s["title"] for s in SLICES}
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-", re.I)
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
        "id": e.get("id"),
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
    weeks = _filter_weeks(weeks)
    keep = {w["slug"] for w in weeks}
    if keep:
        verdicts = [v for v in verdicts if v.get("slice") in keep]
        counts = Counter(v["verdict"] for v in verdicts)
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


def attach_sponsors(blob: dict) -> dict:
    """Recall prior stalls, store open promises, then ask Nemotron only about those rows."""
    from handoff.cache import save_investigation
    from handoff.hmem import recall, remember_open
    from handoff.nemotron import listing_blurb, why_paragraph

    prior = recall(blob.get("name"))
    stored = remember_open(blob)
    blob["memory"] = {**prior, "stored_now": stored}
    why = why_paragraph(blob)
    blob["nemotron"] = why
    blob["listing_blurb"] = listing_blurb(blob, why)
    slim = {k: v for k, v in blob.items() if k != "verdicts"}
    slim["verdicts"] = (blob.get("verdicts") or [])[:40]
    save_investigation(slim)
    return blob


def investigate_text(raw: str, swarm: str) -> dict:
    """Score a pasted transcript. Prefer Zetaris FILESTORE; fall back to memory."""
    from handoff.improve import pack_improve
    from handoff.ingest import ingest_text, normalize

    try:
        meta = ingest_text(raw, swarm)
        blob = investigate_table(meta["table"], swarm)
        blob["ingested"] = meta
        return attach_sponsors(blob)
    except ValueError:
        raise
    except Exception as e:
        rows = normalize(raw, swarm)
        blob = pack("memory", rows, score(rows), swarm)
        blob["warning"] = f"Zetaris register failed, scored in memory: {str(e)[:240]}"
        blob["engine"] = "memory-fallback"
        return attach_sponsors(pack_improve(blob))


def _filter_weeks(weeks: list[dict]) -> list[dict]:
    """Drop CSV-split junk buckets (UUIDs, one-off fragments). Keep named Village weeks."""
    known = [
        w
        for w in weeks
        if w.get("slug") in KNOWN_SLUGS or w.get("title") in KNOWN_TITLES
    ]
    if known:
        return known
    clean = []
    for w in weeks:
        slug = str(w.get("slug") or "")
        title = str(w.get("title") or "")
        n = sum((w.get("counts") or {}).values())
        if UUID_RE.match(slug) or UUID_RE.match(title):
            continue
        if n < 3:
            continue
        if len(slug) > 64 or "\n" in slug:
            continue
        clean.append(w)
    return clean or weeks


def open_promises(blob: dict, limit: int = 40) -> list[dict]:
    rows = [
        v
        for v in blob.get("verdicts") or []
        if v.get("verdict") in ("dropped", "unclaimed", "not_done", "partial")
    ]
    known = KNOWN_SLUGS
    if any(v.get("slice") in known for v in rows):
        rows = [v for v in rows if v.get("slice") in known]
    return rows[:limit]


def investigate_table(table: str, name: str) -> dict:
    from handoff.improve import pack_improve

    rows = fetch_rows(table)
    return pack_improve(pack(table, rows, score(rows), name))

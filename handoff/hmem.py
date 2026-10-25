"""Case memory on the Meterless H-MEM reference engine (hmem/server.ts on 127.0.0.1:8790).

Each verdict is stored once, with its provenance: the promise id and the computer-use turn ids
it was judged against. Recall ranks earlier cases for a new investigation. A reviewer marking a
verdict wrong lowers its confidence through H-MEM's trust ledger, and /audit shows the history.
If the helper is not running, calls say so; nothing is written anywhere else instead.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

INDEX = Path(__file__).resolve().parent.parent / ".handoff" / "hmem_index.json"
DOWN = "H-MEM helper is not running. Start it with: cd hmem && npm run serve"
CONFIDENCE = {"kept": 0.8, "not_done": 0.8, "dropped": 0.6, "partial": 0.6, "unclaimed": 0.6, "unclear": 0.4}


def _base() -> str:
    return os.environ.get("HMEM_URL", "http://127.0.0.1:8790").rstrip("/")


def _call(method: str, path: str, payload: dict | None = None, timeout: float = 10) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(_base() + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode() or "{}")


def health() -> dict:
    try:
        return {"ok": True, **_call("GET", "/health", timeout=3)}
    except (HTTPError, URLError, OSError) as e:
        return {"ok": False, "reason": DOWN, "error": str(e)[:160]}


def _index() -> dict[str, str]:
    if INDEX.is_file():
        return json.loads(INDEX.read_text(encoding="utf-8"))
    return {}


def _save_index(index: dict[str, str]) -> None:
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index), encoding="utf-8")


def remember_verdict(v: dict, index: dict[str, str] | None = None) -> str | None:
    """Store one verdict. Returns the memory id, or None if it was stored before."""
    index = _index() if index is None else index
    key = str(v.get("id"))
    if key in index:
        return None
    speaker = v.get("speaker") or v.get("from") or "unknown"
    verdict = v.get("verdict") or "unclear"
    task = v.get("task") or (v.get("quote") or "")[:120]
    reason = v.get("reason") or v.get("why") or ""
    record = _call(
        "POST",
        "/remember",
        {
            "content": f"{speaker} promised to {task} in {v.get('goal_title') or v.get('slice')}. Verdict: {verdict}. {reason}",
            "source": "handoff:verdict",
            "tags": [str(v.get("slice") or ""), verdict, speaker],
            "refs": [f"promise:{key}"] + [f"turn:{t}" for t in (v.get("turn_ids") or [])],
            "label": "Judged against HANDOFF.cu_turns in Zetaris" if v.get("turn_ids") is not None else "Chat-only verdict",
            "confidence": CONFIDENCE.get(verdict, 0.5),
        },
    )
    index[key] = record["id"]
    return record["id"]


def remember_open(blob: dict, limit: int = 40) -> int:
    if not health().get("ok"):
        return 0
    index = _index()
    n = 0
    for v in blob.get("verdicts") or []:
        if n >= limit:
            break
        if v.get("verdict") not in ("dropped", "unclaimed", "not_done", "partial"):
            continue
        if remember_verdict(v, index):
            n += 1
    _save_index(index)
    return n


def recall(swarm: str | None = None, query: str | None = None, limit: int = 12) -> dict:
    up = health()
    if not up.get("ok"):
        return {"ok": False, "count": 0, "cases": [], "reason": DOWN}
    q = query or f"promises dropped or not done {swarm or ''}".strip()
    out = _call("POST", "/query", {"q": q, "topN": limit, "threshold": 0.05})
    cases = []
    for m in out.get("memories") or []:
        tags = m.get("tags") or ["", "", ""]
        cases.append(
            {
                "id": m.get("id"),
                "verdict": tags[1] if len(tags) > 1 else "",
                "from": tags[2] if len(tags) > 2 else "",
                "quote": m.get("content"),
                "confidence": m.get("confidence"),
                "relevance": m.get("relevance"),
                "refs": (m.get("provenance") or {}).get("refs") or [],
            }
        )
    return {"ok": True, "engine": up.get("engine"), "count": up.get("memories", 0), "cases": cases, "strategy": out.get("strategy")}


def feedback(memory_id: str, kind: str) -> dict:
    return _call("POST", "/feedback", {"id": memory_id, "kind": kind})


def audit(memory_id: str) -> dict:
    return _call("GET", f"/audit/{memory_id}")

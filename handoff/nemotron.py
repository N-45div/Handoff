"""NVIDIA Nemotron through the Meterless Runtime (Nightshift). Never used as the query engine."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from handoff.llm import _endpoint, chat
from handoff.zetaris import load_env

WHY_SYSTEM = (
    "You are Handoff, a swarm post-mortem desk. "
    "Write one short paragraph explaining why this swarm stalled. "
    "Use only the JSON you are given. Quote speaker names. "
    "Do not invent tables, people, or events. "
    "These verdicts come from chat only, so say that the actions were not checked."
)


def ping(timeout: float = 8) -> dict:
    load_env()
    base, headers = _endpoint()
    url = base + "/models"
    try:
        with urlopen(Request(url, headers=headers, method="GET"), timeout=timeout) as resp:
            body = json.loads(resp.read().decode() or "{}")
        ids = [m.get("id") for m in body.get("data") or [] if isinstance(m, dict) and m.get("id")]
        return {"ok": True, "unauthorized": False, "models": ids[:12], "url": url}
    except HTTPError as e:
        if e.code in (401, 403):
            return {"ok": False, "unauthorized": True, "url": url,
                    "error": "Nightshift is up but rejected the token. Put the proxy token in METERLESS_TOKEN."}
        return {"ok": False, "unauthorized": False, "error": f"HTTP {e.code}", "url": url}
    except OSError as e:
        return {"ok": False, "unauthorized": False, "url": url, "detail": str(e)[:180],
                "error": "Nightshift is not running on 127.0.0.1:8088."}


def why_paragraph(blob: dict, private: bool = False) -> dict:
    slim = {
        "name": blob.get("name"),
        "counts": blob.get("counts"),
        "open": [
            {"verdict": v.get("verdict"), "from": v.get("from"), "quote": v.get("quote")}
            for v in (blob.get("verdicts") or [])
            if v.get("verdict") in ("dropped", "unclaimed")
        ][:10],
    }
    res = chat("private" if private else "why",
               [{"role": "system", "content": WHY_SYSTEM},
                {"role": "user", "content": json.dumps(slim, ensure_ascii=False)}],
               max_tokens=600 if private else 2500)
    if not res.get("ok") or not res.get("text"):
        reason = ("No local model is running in Nightshift, so the why was skipped; a private log never goes to a cloud."
                  if private else "Nemotron did not answer through Meterless; the verdicts still stand.")
        return {"ok": False, "skipped": True, "reason": reason, "error": res.get("error")}
    return {"ok": True, "skipped": False, "why": res["text"], "model": res.get("model"), "route": res.get("route"),
            "receipt": res.get("receipt")}


def listing_blurb(blob: dict, why: dict | None = None) -> dict:
    """One sentence a catalog row can show. Only after a cited why, never instead of SQL."""
    if not why or not why.get("ok"):
        return {"ok": False, "skipped": True,
                "reason": (why or {}).get("reason") or "Why paragraph was skipped, so the listing blurb was too."}
    counts = blob.get("counts") or {}
    sentence = (
        f"{blob.get('name') or 'This swarm'}: "
        f"{counts.get('dropped', 0)} dropped, {counts.get('unclaimed', 0)} unclaimed, "
        f"{counts.get('kept', 0)} kept. {why.get('why')}"
    )
    return {"ok": True, "skipped": False, "text": sentence[:420]}


def vl_screen(prompt: str, image_url: str | None = None) -> dict:
    if not image_url:
        return {"ok": False, "skipped": True, "reason": "No screenshot for this promise."}
    content = [
        {"type": "text", "text": "Does this screen show the promised work? Answer yes, no, or unclear, then one sentence. Promise: " + prompt[:400]},
        {"type": "image_url", "image_url": {"url": image_url}},
    ]
    res = chat("vision", [{"role": "user", "content": content}], max_tokens=300)
    if not res.get("ok"):
        return {"ok": False, "skipped": True, "reason": "No vision lane in Meterless; screen proof skipped, not faked.",
                "error": res.get("error")}
    return {"ok": True, "skipped": False, "verdict": res.get("text"), "receipt": res.get("receipt")}


if __name__ == "__main__":
    print(json.dumps(ping(), indent=2))
    print(os.environ.get("METERLESS_BASE_URL", "http://127.0.0.1:8088/v1"))

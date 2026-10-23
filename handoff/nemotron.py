"""NVIDIA Nemotron via Meterless Nightshift. Never used as the query engine."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from handoff.zetaris import load_env

WHY_SYSTEM = (
    "You are Handoff, a swarm post-mortem desk. "
    "Write one short paragraph explaining why this swarm stalled. "
    "Use only the JSON you are given. Quote speaker names. "
    "Do not invent tables, people, or events. "
    "Alibi is prior work that audits past claims; you score promises between agents."
)


def _base() -> str:
    load_env()
    return os.environ.get("METERLESS_BASE_URL", "http://127.0.0.1:8088/v1").rstrip("/")


def _headers() -> dict:
    load_env()
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("METERLESS_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def ping() -> dict:
    url = _base() + "/models"
    try:
        req = Request(url, headers=_headers(), method="GET")
        with urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read().decode() or "{}")
        return {"ok": True, "models": body}
    except Exception as e:
        return {"ok": False, "error": str(e)[:240], "url": url}


def _complete(messages: list[dict], model: str | None = None) -> str:
    load_env()
    model = model or os.environ.get("METERLESS_MODEL") or "nvidia/nemotron"
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 280,
    }
    req = Request(
        _base() + "/chat/completions",
        data=json.dumps(body).encode(),
        headers=_headers(),
        method="POST",
    )
    with urlopen(req, timeout=60) as resp:
        out = json.loads(resp.read().decode() or "{}")
    choices = out.get("choices") or []
    if not choices:
        raise RuntimeError("Nightshift returned no choices")
    return str(choices[0].get("message", {}).get("content") or "").strip()


def why_paragraph(blob: dict) -> dict:
    pinged = ping()
    if not pinged.get("ok"):
        return {
            "ok": False,
            "skipped": True,
            "reason": "Meterless Nightshift is down; Nemotron why skipped.",
            "error": pinged.get("error"),
        }
    slim = {
        "name": blob.get("name"),
        "source": blob.get("source"),
        "counts": blob.get("counts"),
        "weeks": blob.get("weeks"),
        "open": [
            {
                "verdict": v.get("verdict"),
                "from": v.get("from"),
                "slice": v.get("slice"),
                "quote": v.get("quote"),
            }
            for v in (blob.get("verdicts") or [])
            if v.get("verdict") in ("dropped", "unclaimed")
        ][:10],
    }
    try:
        text = _complete(
            [
                {"role": "system", "content": WHY_SYSTEM},
                {"role": "user", "content": json.dumps(slim, ensure_ascii=False)},
            ]
        )
        return {"ok": True, "skipped": False, "model": "nemotron-via-meterless", "why": text}
    except (HTTPError, URLError, OSError, RuntimeError) as e:
        return {
            "ok": False,
            "skipped": True,
            "reason": "Nemotron call failed; Zetaris verdicts still stand.",
            "error": str(e)[:240],
        }


def vl_screen(prompt: str, image_url: str | None = None) -> dict:
    pinged = ping()
    if not pinged.get("ok"):
        return {
            "ok": False,
            "skipped": True,
            "reason": "Nightshift VL down; screen proof skipped.",
            "error": pinged.get("error"),
        }
    if not image_url:
        return {
            "ok": False,
            "skipped": True,
            "reason": "No screen path for this silent drop; did not download computer_use_turns (2.8GB).",
        }
    content = [
        {
            "type": "text",
            "text": (
                "Does this screen show the promised work? Answer yes, no, or unclear, "
                "then one sentence. Promise: "
                + prompt[:400]
            ),
        },
        {"type": "image_url", "image_url": {"url": image_url}},
    ]
    try:
        text = _complete(
            [{"role": "user", "content": content}],
            model=os.environ.get("METERLESS_VL_MODEL") or "nvidia/nemotron-super-vl",
        )
        return {"ok": True, "skipped": False, "verdict": text}
    except (HTTPError, URLError, OSError, RuntimeError) as e:
        return {
            "ok": False,
            "skipped": True,
            "reason": "Nemotron Super-VL failed; not faked.",
            "error": str(e)[:240],
        }

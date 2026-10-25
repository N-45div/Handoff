"""One door for every model call, through the Meterless Runtime (Nightshift) on this machine.

Each step names an NVIDIA Nemotron model on NVIDIA's hosted endpoints, and every answer
carries Meterless's signed compute receipt, which Handoff keeps next to the verdict. The
private step only runs on meterless/local, so a pasted transcript never leaves the machine.
Override a step's model with HANDOFF_<STEP>_MODEL. Nothing falls back silently: a failed
call returns ok=False with the reason.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import deque
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from handoff.zetaris import load_env

# Nemotron 3 Super is not enabled on the NVIDIA trial account (404), so judging uses Ultra.
STEPS = {
    "extract": {"model": "nvidia/nemotron-3.5-lightning-30b-a3b", "thinking": False},
    "judge": {"model": "nvidia/nemotron-3-ultra-550b-a55b", "thinking": True},
    "why": {"model": "nvidia/nemotron-3-ultra-550b-a55b", "thinking": True},
    "vision": {"model": "meterless/vision", "thinking": False},
    "private": {"model": "meterless/local", "thinking": False},
}


def route_for(step: str) -> str:
    return "meterless"


def receipt_of(out: dict) -> dict | None:
    """The fields of a Meterless compute receipt worth showing next to an answer."""
    r = out.get("meterless")
    if not isinstance(r, dict) or not r.get("receipt_id"):
        return None
    win = r.get("winning_route") or {}
    return {
        "receipt_id": r.get("receipt_id"),
        "routed_model": r.get("routed_model"),
        "provider": win.get("provider"),
        "kind": win.get("kind"),
        "ms": sum(p.get("ms") or 0 for p in r.get("phases") or []),
        "usage": r.get("usage"),
        "cost_usd": (r.get("cost") or {}).get("actual_usd"),
        "privacy": r.get("privacy"),
        "egress": r.get("egress"),
    }


def _endpoint(route: str = "meterless") -> tuple[str, dict]:
    base = os.environ.get("METERLESS_BASE_URL", "http://127.0.0.1:8088/v1").rstrip("/")
    headers = {"meterless-app": os.environ.get("METERLESS_APP", "handoff")}
    token = (os.environ.get("METERLESS_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return base, headers


_RATE_LOCK = threading.Lock()
_SENT: deque = deque()


def _pace() -> None:
    """Keep every thread together under NVIDIA's per-minute cap (HANDOFF_RPM, default 30).
    Waiting here is cheaper than hitting the cap and backing off."""
    rpm = int(os.environ.get("HANDOFF_RPM", "30"))
    while True:
        with _RATE_LOCK:
            now = time.time()
            while _SENT and now - _SENT[0] > 60:
                _SENT.popleft()
            if len(_SENT) < rpm:
                _SENT.append(now)
                return
            wait = 60 - (now - _SENT[0]) + 0.05
        time.sleep(wait)


def chat(step: str, messages: list[dict], max_tokens: int = 400, temperature: float = 0.1) -> dict:
    load_env()
    spec = STEPS[step]
    route = route_for(step)
    model = os.environ.get(f"HANDOFF_{step.upper()}_MODEL") or spec["model"]
    base, headers = _endpoint(route)
    body: dict = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    if not spec["thinking"]:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    req_headers = {"Content-Type": "application/json", **headers}
    last = ""
    for attempt in range(5):
        try:
            if not model.startswith("meterless/local"):
                _pace()
            req = Request(base + "/chat/completions", data=json.dumps(body).encode(), headers=req_headers, method="POST")
            t0 = time.time()
            with urlopen(req, timeout=240) as resp:
                out = json.loads(resp.read().decode() or "{}")
            choice = (out.get("choices") or [{}])[0].get("message") or {}
            text = strip_think(str(choice.get("content") or ""))
            receipt = receipt_of(out)
            return {
                "ok": True,
                "text": text,
                "route": route,
                "model": (receipt or {}).get("routed_model") or out.get("model") or model,
                "seconds": round(time.time() - t0, 2),
                "usage": out.get("usage") or {},
                "receipt": receipt,
            }
        except HTTPError as e:
            detail = e.read().decode(errors="replace")
            last = f"HTTP {e.code}: {detail[:200]}"
            # NVIDIA's trial endpoints cap requests per minute; Meterless passes that
            # back as a 502 whose detail says nvidia_429.
            if e.code == 429 or "_429" in detail or '"status":429' in detail:
                time.sleep(10 * (attempt + 1))
                continue
            if e.code in (500, 502, 503, 504):
                time.sleep(2 * (attempt + 1))
                continue
            break
        except (URLError, OSError) as e:
            last = str(getattr(e, "reason", e))[:200]
            time.sleep(2 * (attempt + 1))
    return {"ok": False, "route": route, "model": model, "error": last}


_PROBE: dict = {"at": 0.0, "out": None}


def meterless_ready(max_age: float = 60) -> dict:
    """One-token probe on meterless/fast (ready models only, so it never starts a model load).
    Cached for a minute; Meterless has no provider-status endpoint to read instead."""
    if _PROBE["out"] is not None and time.time() - _PROBE["at"] < max_age:
        return _PROBE["out"]
    load_env()
    base, headers = _endpoint("meterless")
    body = {"model": "meterless/fast", "messages": [{"role": "user", "content": "ok"}], "max_tokens": 1}
    try:
        req = Request(base + "/chat/completions", data=json.dumps(body).encode(),
                      headers={"Content-Type": "application/json", **headers}, method="POST")
        with urlopen(req, timeout=8):
            out = {"up": True, "provider": True}
    except HTTPError as e:
        detail = e.read().decode(errors="replace")
        out = {"up": True, "provider": "no_provider_configured" not in detail,
               "reason": "No provider in Nightshift yet" if "no_provider_configured" in detail else f"HTTP {e.code}"}
    except (URLError, OSError):
        out = {"up": False, "provider": False, "reason": "Nightshift is not running"}
    _PROBE.update(at=time.time(), out=out)
    return out


def strip_think(text: str) -> str:
    # Nemotron 3 Ultra through NVIDIA returns its reasoning inline and closes it with
    # </think>, often without the opening tag.
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def parse_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text or "", flags=re.S)
    if not match:
        return None
    try:
        out = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return out if isinstance(out, dict) else None

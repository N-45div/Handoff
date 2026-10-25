"""One door for every model call, through the Meterless Runtime (Nightshift) on this machine.

Each step names an NVIDIA Nemotron model on NVIDIA's hosted endpoints, and every answer
carries Meterless's signed compute receipt, which Handoff keeps next to the verdict. If
Meterless keeps failing (NVIDIA's trial endpoints rate-limit hard), the same Nemotron model
on Nebius answers instead and the result is marked route="nebius-fallback".
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
    # A pasted log is the user's own data: it is read by a local model through Meterless
    # (Nightshift's Extraction Grid pod) and never falls back to a cloud.
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


# The same Nemotron models hosted on Nebius Token Factory. Used only when Meterless to NVIDIA
# keeps failing (NVIDIA's trial endpoints rate-limit hard); the verdict records the fallback.
NEBIUS_MODELS = {
    "extract": "nvidia/Nemotron-3_5-Lightning",
    "judge": "nvidia/Nemotron-3-Ultra-550b-a55b",
    "why": "nvidia/Nemotron-3-Ultra-550b-a55b",
    "vision": "nvidia/Nemotron-3.5-Super-VL",
}


def _post(base: str, headers: dict, body: dict) -> tuple[dict, float]:
    req = Request(base + "/chat/completions", data=json.dumps(body).encode(),
                  headers={"Content-Type": "application/json", **headers}, method="POST")
    t0 = time.time()
    with urlopen(req, timeout=240) as resp:
        return json.loads(resp.read().decode() or "{}"), time.time() - t0


def _answer(out: dict, route: str, model: str, seconds: float) -> dict:
    choice = (out.get("choices") or [{}])[0].get("message") or {}
    receipt = receipt_of(out)
    return {
        "ok": True,
        "text": strip_think(str(choice.get("content") or "")),
        "route": route,
        "model": (receipt or {}).get("routed_model") or out.get("model") or model,
        "seconds": round(seconds, 2),
        "usage": out.get("usage") or {},
        "receipt": receipt,
    }


def _try(base: str, headers: dict, body: dict, route: str, tries: int, pace: bool) -> tuple[dict | None, str]:
    last = ""
    for attempt in range(tries):
        try:
            if pace:
                _pace()
            out, seconds = _post(base, headers, body)
            return _answer(out, route, body["model"], seconds), ""
        except HTTPError as e:
            detail = e.read().decode(errors="replace")
            last = f"HTTP {e.code}: {detail[:200]}"
            # NVIDIA's trial endpoints cap requests per minute; Meterless passes that
            # back as a 502 whose detail says nvidia_429.
            if e.code == 429 or "_429" in detail or '"status":429' in detail:
                time.sleep(5 * (attempt + 1))
                continue
            if e.code in (500, 502, 503, 504):
                time.sleep(2 * (attempt + 1))
                continue
            break
        except OSError as e:
            last = str(getattr(e, "reason", e))[:200]
            time.sleep(2 * (attempt + 1))
    return None, last


def chat(step: str, messages: list[dict], max_tokens: int = 400, temperature: float = 0.1) -> dict:
    load_env()
    spec = STEPS[step]
    model = os.environ.get(f"HANDOFF_{step.upper()}_MODEL") or spec["model"]
    body: dict = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    if not spec["thinking"]:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    base, headers = _endpoint()
    local = step == "private"
    res, last = _try(base, headers, body, "meterless-local" if local else "meterless", tries=3, pace=not local)
    if res:
        return res
    if local:
        return {"ok": False, "route": "meterless-local", "model": model, "error": last}
    key = (os.environ.get("NEBIUS_API_KEY") or "").strip()
    if key and step in NEBIUS_MODELS:
        nb = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1").rstrip("/")
        res, nlast = _try(nb, {"Authorization": f"Bearer {key}"}, {**body, "model": NEBIUS_MODELS[step]},
                          "nebius-fallback", tries=3, pace=False)
        if res:
            res["fallback_reason"] = last
            return res
        last = f"{last} | fallback: {nlast}"
    return {"ok": False, "route": "meterless", "model": model, "error": last}


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

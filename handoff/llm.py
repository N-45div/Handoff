"""One door for every model call. Each answer records the route and model that produced it.

Routes:
  meterless  the Meterless Runtime on this machine (Nightshift hotspot, OpenAI-compatible)
  nebius     NVIDIA Nemotron hosted on Nebius Token Factory

Pick per step with HANDOFF_<STEP>_ROUTE (extract, judge, why, vision). Default is nebius,
because the Nemotron models do not fit an 8 GB laptop GPU. Nothing falls back silently:
a failed route returns ok=False with the reason.
"""

from __future__ import annotations

import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from handoff.zetaris import load_env

STEPS = {
    "extract": {"nebius": "nvidia/Nemotron-3_5-Lightning", "meterless": "meterless/fast", "thinking": False},
    "judge": {"nebius": "nvidia/nemotron-3-super-120b-a12b", "meterless": "meterless/deep", "thinking": True},
    "why": {"nebius": "nvidia/nemotron-3-super-120b-a12b", "meterless": "meterless/deep", "thinking": True},
    "vision": {"nebius": "nvidia/Nemotron-3.5-Super-VL", "meterless": "meterless/vision", "thinking": False},
}


def route_for(step: str) -> str:
    load_env()
    return (os.environ.get(f"HANDOFF_{step.upper()}_ROUTE") or "nebius").strip().lower()


def _endpoint(route: str) -> tuple[str, dict]:
    if route == "meterless":
        base = os.environ.get("METERLESS_BASE_URL", "http://127.0.0.1:8088/v1").rstrip("/")
        headers = {"meterless-app": os.environ.get("METERLESS_APP", "handoff")}
        token = (os.environ.get("METERLESS_TOKEN") or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return base, headers
    base = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1").rstrip("/")
    key = (os.environ.get("NEBIUS_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("NEBIUS_API_KEY is not set in .env.local")
    return base, {"Authorization": f"Bearer {key}"}


def chat(step: str, messages: list[dict], max_tokens: int = 400, temperature: float = 0.1) -> dict:
    load_env()
    spec = STEPS[step]
    route = route_for(step)
    model = os.environ.get(f"HANDOFF_{step.upper()}_MODEL") or spec[route]
    base, headers = _endpoint(route)
    body: dict = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    if route == "nebius" and not spec["thinking"]:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    req_headers = {"Content-Type": "application/json", **headers}
    last = ""
    for attempt in range(4):
        try:
            req = Request(base + "/chat/completions", data=json.dumps(body).encode(), headers=req_headers, method="POST")
            t0 = time.time()
            with urlopen(req, timeout=240) as resp:
                out = json.loads(resp.read().decode() or "{}")
            choice = (out.get("choices") or [{}])[0].get("message") or {}
            text = strip_think(str(choice.get("content") or ""))
            return {
                "ok": True,
                "text": text,
                "route": route,
                "model": out.get("model") or model,
                "seconds": round(time.time() - t0, 2),
                "usage": out.get("usage") or {},
            }
        except HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode(errors='replace')[:200]}"
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(2 * (attempt + 1))
                continue
            break
        except (URLError, OSError) as e:
            last = str(getattr(e, "reason", e))[:200]
            time.sleep(2 * (attempt + 1))
    return {"ok": False, "route": route, "model": model, "error": last}


def strip_think(text: str) -> str:
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

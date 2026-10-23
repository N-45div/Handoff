"""stdio MCP for Handoff. JSON-RPC with Content-Length framing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from handoff.catalog import load_listings, quote, set_price
from handoff.env_export import episode, write_nightshift
from handoff.improve import suggestions
from handoff.ingest import normalize
from handoff.score import investigate_table, investigate_text, open_promises
from handoff.zetaris import run_sql

LAST: dict | None = None
LAST_ROWS: list = []
ROOT = Path(__file__).resolve().parent.parent


def _tools() -> list[dict]:
    return [
        {
            "name": "handoff_health",
            "description": "Ping Zetaris Lightning SQL.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "handoff_investigate",
            "description": "Score a swarm transcript (speaker + content JSONL/CSV).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "swarm": {"type": "string"},
                    "body": {"type": "string"},
                    "path": {"type": "string"},
                },
            },
        },
        {
            "name": "handoff_open_promises",
            "description": "Dropped and unclaimed promises from the last investigation or Village demo.",
            "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}},
        },
        {
            "name": "handoff_improve",
            "description": "What to change next session, from scored verdicts.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "handoff_catalog",
            "description": "Demo listings with seller list price and 20% Handoff take. Village is never listed.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "list_price_usd": {"type": "number"},
                },
            },
        },
        {
            "name": "handoff_export_env",
            "description": "OpenEnv-shaped episode JSON (handoff-reward@0.1) from Nightshift or last investigation.",
            "inputSchema": {
                "type": "object",
                "properties": {"source": {"type": "string", "enum": ["nightshift", "last"]}},
            },
        },
        {
            "name": "handoff_demo",
            "description": "Village three-week demo already in Zetaris. Not for sale.",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


def _text(obj) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(obj, indent=2)[:24000]}]}


def _call(name: str, args: dict) -> dict:
    global LAST, LAST_ROWS
    args = args or {}
    if name == "handoff_health":
        try:
            ping = run_sql("SELECT 1 AS one", limit=1)
            return _text({"ok": True, "zetaris": True, "select1": ping})
        except Exception as e:
            return _text({"ok": False, "zetaris": False, "error": str(e)[:300]})
    if name == "handoff_investigate":
        body = args.get("body") or ""
        path = args.get("path")
        if path:
            body = Path(path).read_text(encoding="utf-8")
        if not str(body).strip():
            body = (ROOT / "fixtures" / "nightshift-swarm.jsonl").read_text(encoding="utf-8")
        swarm = args.get("swarm") or "swarm"
        LAST_ROWS = normalize(body, swarm)
        LAST = investigate_text(body, swarm)
        slim = {k: LAST[k] for k in LAST if k != "verdicts"}
        slim["verdicts"] = (LAST.get("verdicts") or [])[:20]
        return _text(slim)
    if name == "handoff_demo":
        LAST = investigate_table("HANDOFF.promises", "AI Village — three post-Alibi weeks")
        LAST["for_sale"] = False
        return _text(
            {
                "name": LAST.get("name"),
                "counts": LAST.get("counts"),
                "weeks": LAST.get("weeks"),
                "for_sale": False,
                "improve": LAST.get("improve"),
            }
        )
    if name == "handoff_open_promises":
        blob = LAST or investigate_table("HANDOFF.promises", "AI Village — three post-Alibi weeks")
        return _text(open_promises(blob, int(args.get("limit") or 20)))
    if name == "handoff_improve":
        blob = LAST or {}
        return _text(blob.get("improve") or suggestions(blob.get("verdicts") or []))
    if name == "handoff_catalog":
        if args.get("id") and args.get("list_price_usd") is not None:
            return _text(set_price(str(args["id"]), float(args["list_price_usd"])))
        return _text({"listings": load_listings(), "quote_example": quote(50)})
    if name == "handoff_export_env":
        source = args.get("source") or "nightshift"
        if source == "last" and LAST and LAST_ROWS:
            blob = episode(LAST_ROWS, LAST.get("verdicts") or [], LAST.get("name") or "swarm")
            return _text(blob)
        path = write_nightshift()
        blob = json.loads(path.read_text(encoding="utf-8"))
        return _text({"path": str(path), "terminal_reward": blob.get("terminal_reward"), "steps": len(blob.get("steps") or [])})
    return _text({"error": f"unknown tool {name}"})


def _handle(msg: dict) -> dict | None:
    method = msg.get("method")
    mid = msg.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "handoff", "version": "0.2.0"},
            },
        }
    if method == "notifications/initialized" or method is None:
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": _tools()}}
    if method == "tools/call":
        params = msg.get("params") or {}
        try:
            result = _call(params.get("name") or "", params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": mid, "result": result}
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {"content": [{"type": "text", "text": str(e)[:500]}], "isError": True},
            }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if mid is None:
        return None
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": method}}


def _read() -> dict | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, _, val = line.decode("utf-8").partition(":")
        headers[key.strip().lower()] = val.strip()
    n = int(headers.get("content-length") or "0")
    if n <= 0:
        return None
    raw = sys.stdin.buffer.read(n)
    return json.loads(raw.decode("utf-8"))


def _write(msg: dict) -> None:
    blob = json.dumps(msg).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(blob)}\r\n\r\n".encode("ascii") + blob)
    sys.stdout.buffer.flush()


def main() -> None:
    while True:
        msg = _read()
        if msg is None:
            return
        reply = _handle(msg)
        if reply is not None:
            _write(reply)


if __name__ == "__main__":
    main()

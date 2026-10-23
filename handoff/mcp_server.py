"""stdio MCP: Handoff is the agent that builds tasks from transcripts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from handoff.catalog import load_listings, quote, set_price
from handoff.improve import suggestions
from handoff.score import investigate_table, investigate_text, open_promises
from handoff.secrets import SecretLeak
from handoff.task import build_task
from handoff.zetaris import run_sql

LAST: dict | None = None
LAST_RAW = ""
LAST_NAME = "swarm"
ROOT = Path(__file__).resolve().parent.parent


def _tools() -> list[dict]:
    return [
        {
            "name": "handoff_build_task",
            "description": (
                "Turn a raw swarm or coding-agent transcript into a lab task: "
                "instruction, OpenEnv episode, promise verifier, 20% take if listed. "
                "Village dumps are refused. Secrets (hf_, sk-, .env) are refused."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "swarm": {"type": "string"},
                    "body": {"type": "string"},
                    "path": {"type": "string"},
                    "list_price_usd": {"type": "number"},
                    "source": {"type": "string", "enum": ["body", "last", "nightshift", "coding"]},
                },
            },
        },
        {
            "name": "handoff_health",
            "description": "Ping Zetaris Lightning SQL.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "handoff_investigate",
            "description": "Score promises in a transcript (why the swarm stalled). Does not list a task.",
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
            "description": "Listed tasks. Seller list price, 20% Handoff take. Village is never listed.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "list_price_usd": {"type": "number"},
                },
            },
        },
        {
            "name": "handoff_demo",
            "description": "Village three-week demo in Zetaris. Research only. Not a task. Not for sale.",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


def _text(obj) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(obj, indent=2)[:24000]}]}


def _slim_task(task: dict) -> dict:
    ep = task.get("episode") or {}
    return {
        k: task[k]
        for k in (
            "kind",
            "version",
            "title",
            "prompt",
            "why",
            "license",
            "for_sale",
            "pricing",
            "counts",
            "verifier",
            "improve",
        )
        if k in task
    } | {
        "episode": {
            "env": ep.get("env"),
            "reward_spec": ep.get("reward_spec"),
            "terminal_reward": ep.get("terminal_reward"),
            "steps": len(ep.get("steps") or []),
        }
    }


def _call(name: str, args: dict) -> dict:
    global LAST, LAST_RAW, LAST_NAME
    args = args or {}
    if name == "handoff_health":
        try:
            ping = run_sql("SELECT 1 AS one", limit=1)
            return _text({"ok": True, "zetaris": True, "select1": ping})
        except Exception as e:
            return _text({"ok": False, "zetaris": False, "error": str(e)[:300]})
    if name == "handoff_build_task":
        source = args.get("source") or "body"
        body = args.get("body") or ""
        path = args.get("path")
        swarm = args.get("swarm") or LAST_NAME or "swarm"
        if path:
            body = Path(path).read_text(encoding="utf-8")
        elif source == "last":
            body = LAST_RAW
            swarm = LAST_NAME
        elif source == "nightshift" or not str(body).strip():
            if source == "coding":
                body = (ROOT / "fixtures" / "cursor-pr.jsonl").read_text(encoding="utf-8")
                swarm = args.get("swarm") or "Cursor PR 441"
            else:
                body = (ROOT / "fixtures" / "nightshift-swarm.jsonl").read_text(encoding="utf-8")
                swarm = args.get("swarm") or "Nightshift"
        elif source == "coding":
            body = (ROOT / "fixtures" / "cursor-pr.jsonl").read_text(encoding="utf-8")
            swarm = args.get("swarm") or "Cursor PR 441"
        try:
            task = build_task(body, swarm, list_price_usd=float(args.get("list_price_usd") or 50))
        except SecretLeak as e:
            return {"content": [{"type": "text", "text": str(e)}], "isError": True}
        LAST_RAW = body
        LAST_NAME = swarm
        LAST = {"verdicts": (task.get("verifier") or {}).get("rubric"), "improve": task.get("improve"), "name": swarm}
        return _text(_slim_task(task))
    if name == "handoff_investigate":
        body = args.get("body") or ""
        path = args.get("path")
        if path:
            body = Path(path).read_text(encoding="utf-8")
        if not str(body).strip():
            body = (ROOT / "fixtures" / "nightshift-swarm.jsonl").read_text(encoding="utf-8")
        swarm = args.get("swarm") or "swarm"
        LAST_RAW = body
        LAST_NAME = swarm
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
                "task_blocked": "Village is research-only. Not a listed task.",
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
        return _text({"kind": "handoff-task", "listings": load_listings(), "quote_example": quote(50)})
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
                "serverInfo": {"name": "handoff", "version": "0.3.0"},
                "instructions": (
                    "Handoff builds tasks from agent transcripts. "
                    "Call handoff_build_task. Do not list Village data."
                ),
            },
        }
    if method in ("notifications/initialized", "notifications/cancelled") or method is None:
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": _tools()}}
    if method in ("resources/list", "prompts/list"):
        key = "resources" if method.startswith("resources") else "prompts"
        return {"jsonrpc": "2.0", "id": mid, "result": {key: []}}
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
    first = sys.stdin.buffer.readline()
    if not first:
        return None
    if first.lstrip().startswith(b"{"):
        return json.loads(first.decode("utf-8"))
    headers: dict[str, str] = {}
    key, _, val = first.decode("utf-8").partition(":")
    headers[key.strip().lower()] = val.strip()
    while True:
        line = sys.stdin.buffer.readline()
        if not line or line in (b"\r\n", b"\n"):
            break
        k, _, v = line.decode("utf-8").partition(":")
        headers[k.strip().lower()] = v.strip()
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

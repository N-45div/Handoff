"""Read an agent trace and split what the agents said from what they ran.

A Claude Code session log holds both: the agent's text and the messages it sends to other
agents are talk; every tool call, with its result, is an action. A plain chat export
(speaker + content per line) holds talk only, plus any lines that carry an action/command.

Every string is passed through the secret redactor before it leaves this module.
"""

from __future__ import annotations

import json
import re

from handoff.ingest import normalize
from handoff.secrets import redact

SEND_TOOL = re.compile(r"(reply|send|post|message|comment|notify)", re.I)
SEND_KEYS = ("text", "message", "content", "body")
BAND_FROM = re.compile(r"^From:\s*([^\n(]+)", re.M)
MAX_TEXT = 1500
MAX_ACTION = 400
MAX_OUTPUT = 800


def _lines(raw: str) -> list[dict]:
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            out.append(item)
    return out


def is_claude_code(items: list[dict]) -> bool:
    return any(i.get("type") in ("user", "assistant") and isinstance(i.get("message"), dict) for i in items)


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_text(p) for p in value if not (isinstance(p, dict) and p.get("type") == "image"))
    if isinstance(value, dict):
        return _text(value.get("text") or value.get("content") or "")
    return str(value)


def _describe(name: str, args: dict) -> str:
    """One readable line for a tool call: the command, the file, the query."""
    args = args or {}
    for key in ("command", "file_path", "notebook_path", "url", "query", "pattern", "path"):
        if isinstance(args.get(key), str) and args[key].strip():
            extra = f" {args['path']}" if key == "pattern" and isinstance(args.get("path"), str) else ""
            return f"{args[key]}{extra}"
    return json.dumps(args, ensure_ascii=False)[:MAX_ACTION]


def _sent_text(name: str, args: dict) -> str:
    if not SEND_TOOL.search(name or ""):
        return ""
    for key in SEND_KEYS:
        if isinstance((args or {}).get(key), str) and args[key].strip():
            return args[key]
    return ""


class _Redactor:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self, text: str, limit: int) -> str:
        clean, n = redact((text or "")[: limit * 2])
        self.count += n
        return clean[:limit]


def _claude_code(items: list[dict], name: str, red: _Redactor) -> tuple[list[dict], list[dict], str]:
    agent = next((i.get("agentName") for i in items if i.get("type") == "agent-name" and i.get("agentName")), None) or name
    talk: list[dict] = []
    actions: list[dict] = []
    by_tool: dict[str, dict] = {}
    narration = ""
    for item in items:
        kind = item.get("type")
        if kind not in ("user", "assistant") or item.get("isSidechain"):
            continue
        ts = item.get("timestamp") or ""
        uid = item.get("uuid") or f"r{len(talk) + len(actions)}"
        content = (item.get("message") or {}).get("content")
        parts = content if isinstance(content, list) else [{"type": "text", "text": content or ""}]
        for n, part in enumerate(parts):
            ptype = part.get("type")
            if kind == "assistant" and ptype == "text" and part.get("text", "").strip():
                narration = part["text"]
                talk.append({"id": f"{uid}-{n}", "created_at": ts, "speaker": agent, "channel": "self",
                             "content": red(part["text"], MAX_TEXT)})
            elif kind == "assistant" and ptype == "tool_use":
                tool, args = part.get("name") or "tool", part.get("input") or {}
                row = {"id": part.get("id") or f"{uid}-{n}", "created_at": ts, "speaker": agent,
                       "action_type": tool.split("__")[-1], "action": red(_describe(tool, args), MAX_ACTION),
                       "output": "", "narration": red(narration, 300)}
                actions.append(row)
                by_tool[row["id"]] = row
                sent = _sent_text(tool, args)
                if sent:
                    talk.append({"id": f"{row['id']}:msg", "created_at": ts, "speaker": agent, "channel": "sent",
                                 "content": red(sent, MAX_TEXT)})
                narration = ""
            elif kind == "user" and ptype == "tool_result":
                row = by_tool.get(part.get("tool_use_id") or "")
                if row is not None:
                    row["output"] = red(_text(part.get("content")), MAX_OUTPUT)
            elif kind == "user" and ptype == "text":
                text = (part.get("text") or "").strip()
                if not text or text.startswith("<"):
                    continue  # harness notices, slash-command echoes
                who = BAND_FROM.search(text)
                speaker = who.group(1).strip() if who and text.startswith("[INCOMING") else "user"
                talk.append({"id": f"{uid}-{n}", "created_at": ts, "speaker": speaker, "channel": "received",
                             "content": red(text, MAX_TEXT)})
    return talk, actions, agent


def _plain(raw: str, items: list[dict], name: str, red: _Redactor) -> tuple[list[dict], list[dict], str]:
    talk = [
        {**r, "channel": "chat", "content": red(r["content"], MAX_TEXT)}
        for r in normalize(raw, name)
    ]
    actions = []
    for i, item in enumerate(items, 1):
        act = item.get("action") or item.get("command")
        if isinstance(act, str) and act.strip():
            actions.append({
                "id": str(item.get("id") or f"a{i}"),
                "created_at": str(item.get("created_at") or item.get("timestamp") or ""),
                "speaker": str(item.get("speaker") or item.get("agent") or "agent"),
                "action_type": str(item.get("action_type") or item.get("tool") or "action"),
                "action": red(act, MAX_ACTION),
                "output": red(_text(item.get("output")), MAX_OUTPUT),
                "narration": "",
            })
    speakers = {a["speaker"] for a in actions} or {r["speaker"] for r in talk}
    return talk, actions, ", ".join(sorted(speakers))


def parse(raw: str, name: str) -> dict:
    """{"format", "agent", "talk": [...], "actions": [...], "redacted": n} in time order."""
    items = _lines(raw)
    red = _Redactor()
    if items and is_claude_code(items):
        talk, actions, agent = _claude_code(items, name, red)
        fmt = "claude-code"
    else:
        talk, actions, agent = _plain(raw, items, name, red)
        fmt = "chat"
    return {"format": fmt, "agent": agent, "talk": talk, "actions": actions, "redacted": red.count}

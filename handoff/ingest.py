"""Normalize any swarm chat export and register it as a Zetaris FILESTORE table."""

from __future__ import annotations

import csv
import json
import re
import subprocess
import uuid
from io import StringIO
from pathlib import Path

from handoff.fetch import data_dir
from handoff.zetaris import run_sql

CONTAINER = "zetaris-driver-1"
REMOTE_DIR = "/home/zetaris/customer-data/shared/handoff"
FIELDS = ("id", "created_at", "speaker", "content", "slice_slug", "goal_id", "goal_title")
SPEAKER_KEYS = ("speaker", "from", "agent", "author", "name", "role", "user")
TEXT_KEYS = ("content", "text", "message", "body", "quote")
TIME_KEYS = ("created_at", "timestamp", "ts", "time", "at", "datetime")
SWARM_KEYS = ("slice_slug", "swarm", "goal", "goal_title", "room", "channel", "thread")


def ident(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_")
    if not slug or slug[0].isdigit():
        slug = "s_" + slug
    return slug[:40].lower()


def _text_of(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return " ".join(_text_of(part) for part in value).strip()
    if isinstance(value, dict):
        if value.get("text") or value.get("content"):
            return _text_of(value.get("text") or value.get("content"))
        if value.get("type") == "tool_use":
            return f"I'll use {value.get('name') or 'a tool'}."
    return ""


def flatten_row(src: dict) -> dict:
    """Coding-agent exports (Cursor / Claude Code) add extra keys. Keep speaker+content."""
    row = dict(src)
    msg = row.get("message")
    if isinstance(msg, dict):
        row.setdefault("role", msg.get("role"))
        if not row.get("content"):
            row["content"] = msg.get("content")
        if not row.get("speaker"):
            row["speaker"] = msg.get("speaker") or msg.get("name")
    row["content"] = _text_of(row.get("content") or row.get("text") or row.get("message"))
    if not row["content"] and row.get("type") == "tool_use":
        row["content"] = f"I'll use {row.get('name') or 'a tool'}."
        row.setdefault("role", "assistant")
    return row


def _pick(row: dict, keys: tuple[str, ...]) -> str:
    lower = {str(k).lower(): v for k, v in row.items()}
    for k in keys:
        v = lower.get(k)
        text = _text_of(v)
        if text:
            return text
    return ""


def parse_export(raw: str) -> list[dict]:
    text = raw.strip()
    if not text:
        return []
    rows: list[dict] = []
    if text[0] in "[{":
        try:
            blob = json.loads(text)
            if isinstance(blob, dict):
                blob = blob.get("messages") or blob.get("rows") or [blob]
            for item in blob:
                if isinstance(item, dict):
                    rows.append(flatten_row(item))
            return rows
        except json.JSONDecodeError:
            pass
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(flatten_row(item))
        if rows:
            return rows
    reader = csv.DictReader(StringIO(text))
    return [flatten_row(dict(r)) for r in reader]


def normalize(raw: str, swarm_name: str) -> list[dict]:
    slug = ident(swarm_name).lower()
    out = []
    for i, src in enumerate(parse_export(raw), 1):
        speaker = _pick(src, SPEAKER_KEYS)
        content = _pick(src, TEXT_KEYS)
        if not content:
            continue
        swarm = _pick(src, SWARM_KEYS) or slug
        out.append(
            {
                "id": str(src.get("id") or f"{slug}-{i}"),
                "created_at": _pick(src, TIME_KEYS) or f"2026-01-01 00:00:{i:02d}",
                "speaker": speaker or f"agent-{i}",
                "content": content,
                "slice_slug": ident(swarm).lower(),
                "goal_id": str(src.get("goal_id") or slug),
                "goal_title": swarm_name,
            }
        )
    return out


def write_csv(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) or "" for k in FIELDS})
    return path


def copy_into_driver(local: Path, remote_name: str) -> str:
    remote = f"{REMOTE_DIR}/{remote_name}"
    subprocess.run(["docker", "exec", CONTAINER, "mkdir", "-p", REMOTE_DIR], check=True)
    subprocess.run(["docker", "cp", str(local), f"{CONTAINER}:{remote}"], check=True)
    return remote


def _sql_ok(sql: str) -> None:
    try:
        run_sql(sql, limit=5)
    except RuntimeError as e:
        if "already exists" not in str(e).lower():
            raise


def register_table(table: str, remote_path: str) -> None:
    _sql_ok('CREATE LIGHTNING DATABASE HANDOFF DESCRIBE BY "Handoff swarm investigations"')
    _sql_ok(
        f"CREATE LIGHTNING FILESTORE TABLE {table} FROM HANDOFF FORMAT CSV OPTIONS ("
        f"PATH \"{remote_path}\", inferSchema \"true\", header \"true\", multiLine \"true\")"
    )


def ingest_text(raw: str, swarm_name: str) -> dict:
    rows = normalize(raw, swarm_name)
    if len(rows) < 2:
        raise ValueError("Need at least two chat lines with a speaker and a message.")
    table = ident(swarm_name + "_" + uuid.uuid4().hex[:6])
    local = data_dir() / "uploads" / f"{table.lower()}.csv"
    write_csv(rows, local)
    remote = copy_into_driver(local, local.name)
    register_table(table, remote)
    return {"table": f"HANDOFF.{table}", "rows": len(rows), "file": str(local)}

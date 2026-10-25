"""Stream computer_use_turns (2.8 GB gz) once and keep the three weeks as Parquet.

Executed actions and tool output are the evidence. The model's own narration is kept
short and only helps locate the work: an agent saying it sent the email is not proof.
"""

from __future__ import annotations

import gzip
import json
import os
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv
from huggingface_hub import hf_hub_url

from handoff.fetch import REPO, data_dir, download, read_jsonl_gz
from handoff.goals import SLICES
from handoff.slice import agent_names

TURNS = "computer_use_turns.jsonl.gz"
SESSIONS = "computer_use_sessions.jsonl.gz"
TEXT_KEYS = ("text", "thinking", "reasoning", "content", "summary")
SCHEMA = pa.schema(
    [
        ("id", pa.string()),
        ("session_id", pa.string()),
        ("created_at", pa.string()),
        ("speaker", pa.string()),
        ("slice_slug", pa.string()),
        ("action_type", pa.string()),
        ("action", pa.string()),
        ("output", pa.string()),
        ("error", pa.string()),
        ("narration", pa.string()),
        ("has_screenshot", pa.bool_()),
    ]
)
WINDOWS = [(s["start"][:19], s["end"][:19], s["slug"]) for s in SLICES]


def session_speakers() -> dict[str, str]:
    raw = data_dir() / "raw" / SESSIONS
    if not raw.exists():
        raw = download(SESSIONS)
    names = agent_names()
    out = {}
    for row in read_jsonl_gz(raw):
        aid = str(row.get("agent_id") or "")
        out[str(row.get("id"))] = names.get(aid) or aid
    return out


def window_slug(created_at: str) -> str | None:
    ts = (created_at or "").replace("T", " ")[:19]
    for start, end, slug in WINDOWS:
        if start <= ts < end:
            return slug
    return None


def _strings(obj, out: list[str], budget: int) -> None:
    if sum(len(s) for s in out) >= budget:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("signature", "data", "image", "source", "base64"):
                continue
            if isinstance(v, str) and k in TEXT_KEYS and v.strip():
                out.append(v.strip())
            else:
                _strings(v, out, budget)
    elif isinstance(obj, list):
        for v in obj:
            _strings(v, out, budget)


def narration(messages, budget: int = 700) -> str:
    parts: list[str] = []
    _strings(messages, parts, budget)
    return " ".join(" ".join(parts).split())[:budget]


def describe_action(action) -> tuple[str, str]:
    if not action:
        return "talk", ""
    if isinstance(action, dict):
        if action.get("command"):
            return "bash", str(action["command"])[:500]
        kind = str(action.get("action") or "action")
        rest = {k: v for k, v in action.items() if k not in ("action", "coordinate")}
        return kind, (json.dumps(rest, ensure_ascii=False) if rest else "")[:500]
    return "action", str(action)[:500]


def stream_lines(name: str):
    load_dotenv()
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    req = Request(hf_hub_url(REPO, name, repo_type="dataset"), headers={"Authorization": f"Bearer {token}"})
    with urlopen(req, timeout=120) as resp, gzip.GzipFile(fileobj=resp) as gz:
        for line in gz:
            if line.strip():
                yield line


def main() -> None:
    speakers = session_speakers()
    dest = data_dir() / "slices" / "cu_turns.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    writer = pq.ParquetWriter(dest, SCHEMA, compression="zstd")
    batch: list[dict] = []
    seen = kept = 0
    counts = {s["slug"]: 0 for s in SLICES}
    t0 = time.time()
    try:
        for line in stream_lines(TURNS):
            seen += 1
            if seen % 100_000 == 0:
                print(f"{seen:,} read, {kept:,} kept, {time.time() - t0:.0f}s", file=sys.stderr, flush=True)
            row = json.loads(line)
            slug = window_slug(str(row.get("created_at") or ""))
            if slug is None:
                continue
            kind, action = describe_action(row.get("agent_action"))
            batch.append(
                {
                    "id": str(row.get("id") or ""),
                    "session_id": str(row.get("session_id") or ""),
                    "created_at": str(row.get("created_at") or ""),
                    "speaker": speakers.get(str(row.get("session_id")), ""),
                    "slice_slug": slug,
                    "action_type": kind,
                    "action": action,
                    "output": str(row.get("output") or "")[:400],
                    "error": str(row.get("error") or "")[:200],
                    "narration": narration(row.get("agent_messages")),
                    "has_screenshot": not bool(row.get("screenshot_is_redacted"))
                    or bool(row.get("has_redaction_been_overruled")),
                }
            )
            kept += 1
            counts[slug] += 1
            if len(batch) >= 5000:
                writer.write_table(pa.Table.from_pylist(batch, schema=SCHEMA))
                batch.clear()
        if batch:
            writer.write_table(pa.Table.from_pylist(batch, schema=SCHEMA))
    finally:
        writer.close()
    print(f"wrote {dest}: {kept:,} turns of {seen:,} in {time.time() - t0:.0f}s", file=sys.stderr)
    for slug, n in counts.items():
        print(f"  {slug}: {n:,}", file=sys.stderr)


if __name__ == "__main__":
    main()

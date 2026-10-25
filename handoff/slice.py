"""Cut the three post-Alibi weeks from chat into gitignored JSONL and CSV."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from handoff.fetch import CHAT, data_dir, download, read_jsonl_gz
from handoff.goals import SLICES, window_for


KEEP = ("id", "created_at", "speaker", "agent_speaker_id", "speaker_type", "room_id", "content")


def agent_names() -> dict[str, str]:
    path = data_dir() / "raw" / "agents.jsonl.gz"
    if not path.exists():
        path = download("agents.jsonl.gz")
    names = {}
    for row in read_jsonl_gz(path):
        ident = row.get("id")
        if ident:
            names[str(ident)] = row.get("name") or row.get("model_string") or str(ident)
    return names


def slice_chat() -> Path:
    names = agent_names()
    raw = data_dir() / "raw" / CHAT
    if not raw.exists():
        raw = download(CHAT)
    out_dir = data_dir() / "slices"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "chat_messages.jsonl"
    csv_dest = out_dir / "chat_messages.csv"
    counts = {s["slug"]: 0 for s in SLICES}
    n = 0
    rows = []
    fields = list(KEEP) + ["slice_slug", "goal_id", "goal_title"]
    with dest.open("w", encoding="utf-8") as fh, csv_dest.open(
        "w", encoding="utf-8", newline=""
    ) as cf:
        writer = csv.DictWriter(cf, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for msg in read_jsonl_gz(raw):
            if msg.get("speaker_type") != "agent":
                continue
            win = window_for(msg.get("created_at"))
            if win is None:
                continue
            row = {k: msg.get(k) or "" for k in KEEP}
            aid = str(msg.get("agent_speaker_id") or "")
            row["agent_speaker_id"] = aid
            row["speaker"] = names.get(aid) or aid
            row["room_id"] = msg.get("room_id") or ""
            row["slice_slug"] = win["slug"]
            row["goal_id"] = win["id"]
            row["goal_title"] = win["title"]
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            writer.writerow(row)
            rows.append({k: str(row.get(k) or "") for k in fields})
            counts[win["slug"]] += 1
            n += 1
    # Zetaris reads CSV with backslash escapes, so quoted chat splits rows. Parquet cannot.
    pq.write_table(pa.Table.from_pylist(rows), out_dir / "chat_messages.parquet", compression="zstd")
    print(f"wrote {dest}, {csv_dest} and chat_messages.parquet ({n} agent rows)", file=sys.stderr)
    for slug, c in counts.items():
        print(f"  {slug}: {c}", file=sys.stderr)
    return csv_dest


def main() -> None:
    slice_chat()


if __name__ == "__main__":
    main()

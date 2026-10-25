"""Stream agent_memories (2.5 GB gz) once and keep the three weeks as Parquet.

A memory is the note an agent writes for its future self between sessions. Handoff asks
whether a promise that made it into that note was kept more often than one left in chat.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import timedelta

import pyarrow as pa
import pyarrow.parquet as pq

from handoff.fetch import data_dir
from handoff.goals import SLICES, parse_ts
from handoff.slice import agent_names
from handoff.turns import stream_lines

MEMORIES = "agent_memories.jsonl.gz"
SCHEMA = pa.schema(
    [
        ("id", pa.string()),
        ("created_at", pa.string()),
        ("speaker", pa.string()),
        ("slice_slug", pa.string()),
        ("content", pa.string()),
    ]
)
# A promise made late in a week can be written down after the week ends.
WINDOWS = [
    (s["start"][:19], (parse_ts(s["end"]) + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"), s["slug"])
    for s in SLICES
]


def window_slug(created_at: str) -> str | None:
    ts = (created_at or "").replace("T", " ")[:19]
    for start, end, slug in WINDOWS:
        if start <= ts < end:
            return slug
    return None


def main() -> None:
    names = agent_names()
    dest = data_dir() / "slices" / "memories.parquet"
    writer = pq.ParquetWriter(dest, SCHEMA, compression="zstd")
    batch: list[dict] = []
    seen = kept = 0
    t0 = time.time()
    try:
        for line in stream_lines(MEMORIES):
            seen += 1
            if seen % 20_000 == 0:
                print(f"{seen:,} read, {kept:,} kept, {time.time() - t0:.0f}s", file=sys.stderr, flush=True)
            row = json.loads(line)
            slug = window_slug(str(row.get("created_at") or ""))
            if slug is None:
                continue
            aid = str(row.get("agent_id") or "")
            batch.append(
                {
                    "id": str(row.get("id") or ""),
                    "created_at": str(row.get("created_at") or ""),
                    "speaker": names.get(aid) or aid,
                    "slice_slug": slug,
                    "content": str(row.get("content") or "")[:30000],
                }
            )
            kept += 1
            if len(batch) >= 500:
                writer.write_table(pa.Table.from_pylist(batch, schema=SCHEMA))
                batch.clear()
        if batch:
            writer.write_table(pa.Table.from_pylist(batch, schema=SCHEMA))
    finally:
        writer.close()
    print(f"wrote {dest}: {kept:,} memories of {seen:,} in {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()

"""Stream small Village tables into gitignored ./data. Never commit the dump."""

from __future__ import annotations

import gzip
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import hf_hub_download

REPO = "aidigestorg/ai-village"
CATALOG = ("village_goals.jsonl.gz", "agents.jsonl.gz", "agent_goals.jsonl.gz", "chat_rooms.jsonl.gz")


def data_dir() -> Path:
    load_dotenv()
    root = Path(os.environ.get("HANDOFF_DATA_DIR", "./data"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def download(name: str) -> Path:
    dest_dir = data_dir()
    path = hf_hub_download(
        repo_id=REPO,
        repo_type="dataset",
        filename=name,
        local_dir=str(dest_dir / "raw"),
    )
    return Path(path)


def read_jsonl_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def catalog() -> None:
    for name in CATALOG:
        path = download(name)
        print(f"ok {name} -> {path}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "catalog"
    if cmd == "catalog":
        catalog()
        return
    print("usage: python -m handoff.fetch catalog", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()

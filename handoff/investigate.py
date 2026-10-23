"""CLI: score a Zetaris swarm table. Default is the Village demo."""

from __future__ import annotations

import json
import sys

from handoff.fetch import data_dir
from handoff.score import investigate_table

TABLE = "HANDOFF.promises"


def main() -> None:
    table = sys.argv[1] if len(sys.argv) > 1 else TABLE
    name = sys.argv[2] if len(sys.argv) > 2 else "Village demo"
    summary = investigate_table(table, name)
    out = data_dir() / "verdicts.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    print(json.dumps(summary["counts"]))


if __name__ == "__main__":
    main()

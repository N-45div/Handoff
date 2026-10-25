"""Copy the chat slice into the Zetaris volume and run FILESTORE DDL."""

from __future__ import annotations

import subprocess
from pathlib import Path

from handoff.fetch import data_dir
from handoff.zetaris import run_sql

CONTAINER = "zetaris-driver-1"
REMOTE_DIR = "/home/zetaris/customer-data/shared/handoff"
DDL = Path(__file__).resolve().parent.parent / "sql" / "01_handoff_filestore.sql"
FILES = ("chat_messages.parquet", "cu_sessions.csv", "cu_turns.parquet", "memories.parquet")


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def copy_slice() -> None:
    _run(["docker", "exec", CONTAINER, "mkdir", "-p", REMOTE_DIR])
    for name in FILES:
        src = data_dir() / "slices" / name
        if not src.is_file():
            print(f"skip copy, missing {src}")
            continue
        remote = f"{REMOTE_DIR}/{name}"
        _run(["docker", "cp", str(src), f"{CONTAINER}:{remote}"])
        print(f"copied {src} -> {CONTAINER}:{remote}")


def statements(text: str) -> list[str]:
    out = []
    for raw in text.split(";"):
        lines = [ln for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("--")]
        sql = "\n".join(lines).strip()
        if sql:
            out.append(sql)
    return out


def register() -> None:
    for sql in statements(DDL.read_text(encoding="utf-8")):
        print(f"sql: {sql[:90]}...")
        try:
            print(run_sql(sql, limit=20))
        except RuntimeError as e:
            msg = str(e).lower()
            if any(
                tok in msg
                for tok in (
                    "already exists",
                    "does not exist",
                    "cannot find",
                    "key not found",
                    "table or view not found",
                )
            ):
                print(f"skip: {e}")
            else:
                raise


def main() -> None:
    copy_slice()
    register()
    print(run_sql("SHOW LIGHTNING DATABASES", limit=20))
    print("promises", run_sql("SELECT COUNT(*) AS n FROM HANDOFF.promises", limit=5))
    try:
        print("cu_sessions", run_sql("SELECT COUNT(*) AS n FROM HANDOFF.cu_sessions", limit=5))
    except RuntimeError as e:
        print("cu_sessions not ready:", e)


if __name__ == "__main__":
    main()

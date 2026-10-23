"""Handoff desk — investigate any agent swarm through Zetaris."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from handoff.ingest import ingest_text
from handoff.score import investigate_table, pack, score
from handoff.zetaris import run_sql

WEB = Path(__file__).resolve().parent / "web"
DEMO_TABLE = "HANDOFF.promises"
SAMPLE = Path(__file__).resolve().parent.parent / "fixtures" / "nightshift-swarm.jsonl"

app = FastAPI(title="Handoff", version="0.2.0")
app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.get("/api/health")
def health() -> dict:
    try:
        ping = run_sql("SELECT 1 AS one", limit=1)
        dbs = run_sql("SHOW LIGHTNING DATABASES", limit=20)
        return {"ok": True, "zetaris": True, "select1": ping, "databases": dbs}
    except Exception as e:
        return {"ok": False, "zetaris": False, "error": str(e)[:300]}


@app.get("/api/demo")
def demo() -> dict:
    try:
        return investigate_table(DEMO_TABLE, "AI Village — three post-Alibi weeks")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)[:400]) from e


@app.get("/api/sample")
def sample() -> dict:
    if not SAMPLE.is_file():
        raise HTTPException(status_code=404, detail="sample fixture missing")
    return {
        "name": "Nightshift",
        "hint": "A tiny synthetic swarm so testers do not need the Village dump.",
        "body": SAMPLE.read_text(encoding="utf-8"),
    }


@app.post("/api/investigate")
async def investigate(
    swarm: str = Form("new-swarm"),
    file: UploadFile | None = File(None),
    body: str = Form(""),
) -> dict:
    raw = body
    if file is not None:
        raw = (await file.read()).decode("utf-8", errors="replace")
    if not raw.strip():
        raise HTTPException(status_code=400, detail="Paste JSONL/CSV or attach a file.")
    try:
        meta = ingest_text(raw, swarm)
        result = investigate_table(meta["table"], swarm)
        result["ingested"] = meta
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        # Still score locally if FILESTORE registration fails, but say so.
        from handoff.ingest import normalize

        rows = normalize(raw, swarm)
        packed = pack("memory", rows, score(rows), swarm)
        packed["warning"] = f"Zetaris register failed, scored in memory: {str(e)[:240]}"
        packed["engine"] = "memory-fallback"
        return packed


def main() -> None:
    import uvicorn

    uvicorn.run("handoff.app:app", host="127.0.0.1", port=8787, reload=False)


if __name__ == "__main__":
    main()

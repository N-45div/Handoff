"""Handoff desk — investigate any agent swarm through Zetaris."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from handoff.catalog import load_listings, quote, set_price
from handoff.env_export import episode, write_nightshift
from handoff.ingest import normalize
from handoff.score import investigate_table, investigate_text, score

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
        from handoff.zetaris import run_sql

        ping = run_sql("SELECT 1 AS one", limit=1)
        dbs = run_sql("SHOW LIGHTNING DATABASES", limit=20)
        return {"ok": True, "zetaris": True, "select1": ping, "databases": dbs}
    except Exception as e:
        return {"ok": False, "zetaris": False, "error": str(e)[:300]}


@app.get("/api/demo")
def demo() -> dict:
    try:
        blob = investigate_table(DEMO_TABLE, "AI Village — three post-Alibi weeks")
        blob["for_sale"] = False
        return blob
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


@app.get("/api/catalog")
def catalog() -> dict:
    return {
        "take_rate": 0.20,
        "village_forbidden": True,
        "listings": load_listings(),
        "quote_example": quote(50),
    }


@app.post("/api/catalog/price")
def catalog_price(listing_id: str = Form(...), list_price_usd: float = Form(...)) -> dict:
    try:
        return set_price(listing_id, list_price_usd)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"unknown listing {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/env/nightshift")
def env_nightshift() -> dict:
    path = write_nightshift()
    return json_episode(path)


def json_episode(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/api/env/export")
async def env_export(
    swarm: str = Form("new-swarm"),
    file: UploadFile | None = File(None),
    body: str = Form(""),
) -> dict:
    raw = body
    if file is not None:
        raw = (await file.read()).decode("utf-8", errors="replace")
    if not raw.strip():
        raise HTTPException(status_code=400, detail="Paste JSONL/CSV or attach a file.")
    rows = normalize(raw, swarm)
    return episode(rows, score(rows), swarm)


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
        return investigate_text(raw, swarm)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def main() -> None:
    import uvicorn

    uvicorn.run("handoff.app:app", host="127.0.0.1", port=8787, reload=False)


if __name__ == "__main__":
    main()

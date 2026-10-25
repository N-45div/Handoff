"""Handoff desk — investigate a transcript, then build a task."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from handoff.catalog import load_listings, quote, set_price
from handoff.env_export import write_nightshift
from handoff.score import attach_sponsors, investigate_table, investigate_text
from handoff.secrets import SecretLeak
from handoff.task import build_task

WEB = Path(__file__).resolve().parent / "web"
ROOT = Path(__file__).resolve().parent.parent
DEMO_TABLE = "HANDOFF.promises"
SAMPLES = {
    "nightshift": (ROOT / "fixtures" / "nightshift-swarm.jsonl", "Nightshift"),
    "coding": (ROOT / "fixtures" / "cursor-pr.jsonl", "Cursor PR 441"),
}

app = FastAPI(title="Handoff", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.get("/desk")
def desk() -> FileResponse:
    return FileResponse(WEB / "desk.html")


@app.get("/api/health")
def health() -> dict:
    from handoff.nemotron import ping as night_ping

    from handoff.hmem import health as hmem_health

    night = night_ping(timeout=2)
    mem = hmem_health()
    out = {
        "nightshift": bool(night.get("ok")),
        "nightshift_unauthorized": bool(night.get("unauthorized")),
        "nightshift_error": night.get("error"),
        "hmem": bool(mem.get("ok")),
        "hmem_memories": mem.get("memories"),
    }
    try:
        from handoff.zetaris import run_sql

        ping = run_sql("SELECT 1 AS one", limit=1)
        return {"ok": True, "zetaris": True, "select1": ping, **out}
    except Exception as e:
        return {"ok": False, "zetaris": False, "error": str(e)[:300], **out}


@app.get("/api/demo")
def demo() -> dict:
    from handoff.village import investigation

    try:
        return investigation()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)[:400]) from e


@app.get("/api/turns")
def turns(ids: str = Query("")) -> dict:
    from handoff.village import cited_turns

    try:
        return {"turns": cited_turns([i.strip() for i in ids.split(",") if i.strip()])}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)[:400]) from e


@app.post("/api/feedback")
def verdict_feedback(promise_id: str = Form(...), kind: str = Form(...)) -> dict:
    from handoff.hmem import _index, audit, feedback

    if kind not in ("helpful", "not_helpful", "wrong"):
        raise HTTPException(status_code=400, detail="kind must be helpful, not_helpful or wrong")
    memory_id = _index().get(promise_id)
    if not memory_id:
        raise HTTPException(status_code=404, detail="This verdict is not in H-MEM yet.")
    try:
        return {"memory": feedback(memory_id, kind), "audit": audit(memory_id)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"H-MEM: {str(e)[:200]}") from e


@app.get("/api/audit")
def verdict_audit(promise_id: str = Query(...)) -> dict:
    from handoff.hmem import _index, audit

    memory_id = _index().get(promise_id)
    if not memory_id:
        raise HTTPException(status_code=404, detail="This verdict is not in H-MEM yet.")
    return {"memory_id": memory_id, **audit(memory_id)}


@app.get("/api/sample")
def sample(kind: str = Query("nightshift")) -> dict:
    key = kind if kind in SAMPLES else "nightshift"
    path, name = SAMPLES[key]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="sample fixture missing")
    return {"name": name, "kind": key, "body": path.read_text(encoding="utf-8")}


@app.get("/api/catalog")
def catalog() -> dict:
    return {
        "take_rate": 0.20,
        "kind": "handoff-task",
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
    return json.loads(path.read_text(encoding="utf-8"))


def _read_body(body: str, file: UploadFile | None, raw: bytes | None) -> str:
    if raw:
        return raw.decode("utf-8", errors="replace")
    return body


@app.post("/api/task")
async def make_task(
    swarm: str = Form("new-swarm"),
    list_price_usd: float = Form(50),
    file: UploadFile | None = File(None),
    body: str = Form(""),
) -> dict:
    raw = body
    if file is not None:
        raw = (await file.read()).decode("utf-8", errors="replace")
    if not raw.strip():
        raise HTTPException(status_code=400, detail="Paste JSONL/CSV or attach a file.")
    try:
        return build_task(raw, swarm, list_price_usd=list_price_usd)
    except SecretLeak as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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

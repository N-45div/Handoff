"""Demo catalog. Seller sets list price. Handoff takes 20%. Village is never listed."""

from __future__ import annotations

import json
from pathlib import Path

TAKE_RATE = 0.20
ROOT = Path(__file__).resolve().parent.parent
LISTINGS_PATH = ROOT / "fixtures" / "catalog.json"
FORBIDDEN = ("ai-village", "aidigestorg", "aidigest", "handoff.promises")


def quote(list_price_usd: float) -> dict:
    price = round(float(list_price_usd), 2)
    if price < 0:
        raise ValueError("list price must be >= 0")
    take = round(price * TAKE_RATE, 2)
    return {
        "list_price_usd": price,
        "take_rate": TAKE_RATE,
        "platform_take_usd": take,
        "seller_payout_usd": round(price - take, 2),
    }


def _default_listings() -> list[dict]:
    return [
        {
            "id": "nightshift-handoff-demo",
            "title": "Nightshift deploy swarm (synthetic)",
            "seller": "handoff-demo",
            "list_price_usd": 50,
            "license": "demo-not-for-training",
            "source": "fixtures/nightshift-swarm.jsonl",
            "episode": "fixtures/openenv/nightshift-episode.json",
            "notes": "Fixture swarm. Not Village. Not for model training.",
        }
    ]


def load_listings() -> list[dict]:
    if LISTINGS_PATH.is_file():
        blob = json.loads(LISTINGS_PATH.read_text(encoding="utf-8"))
        rows = blob.get("listings") if isinstance(blob, dict) else blob
        if isinstance(rows, list) and rows:
            return [enrich(x) for x in rows if allowed(x)]
    return [enrich(x) for x in _default_listings()]


def allowed(listing: dict) -> bool:
    hay = " ".join(str(listing.get(k) or "") for k in ("id", "source")).lower()
    return not any(bad in hay for bad in FORBIDDEN)


def enrich(listing: dict) -> dict:
    money = quote(listing.get("list_price_usd") or 0)
    return {**listing, **money, "for_sale": allowed(listing)}


def _canon(listing: dict) -> dict:
    keys = ("id", "title", "seller", "list_price_usd", "license", "source", "episode", "notes")
    return {k: listing.get(k) for k in keys}


def set_price(listing_id: str, list_price_usd: float) -> dict:
    rows = [_canon(x) for x in load_listings()]
    found = None
    for row in rows:
        if row.get("id") == listing_id:
            row["list_price_usd"] = round(float(list_price_usd), 2)
            found = enrich(row)
            break
    if found is None:
        raise KeyError(listing_id)
    LISTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LISTINGS_PATH.write_text(
        json.dumps({"take_rate": TAKE_RATE, "listings": rows}, indent=2) + "\n",
        encoding="utf-8",
    )
    return found

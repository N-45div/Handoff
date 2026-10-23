"""The three post-Alibi weeks we investigate. Chat is the contract."""

from __future__ import annotations

from datetime import datetime

SLICES = (
    {
        "slug": "organise_event",
        "id": "fad5b22b-c030-4262-8cb0-7cf424c7c236",
        "title": "Organise an event!",
        "start": "2026-06-08 09:30:58",
        "end": "2026-06-15 11:26:56",
    },
    {
        "slug": "best_assistant",
        "id": "680a1b42-e1e2-45ea-b4d7-50764eb0523e",
        "title": "Compete to be the best AI Assistant!",
        "start": "2026-06-29 09:22:34",
        "end": "2026-07-06 15:59:00",
    },
    {
        "slug": "finetune_leader",
        "id": "b3f1d47d-4274-446b-8bd1-6fdaa041d313",
        "title": "Finetune your leader!",
        "start": "2026-05-26 11:37:17",
        "end": "2026-06-01 15:19:23",
    },
)


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("T", " ").split("+")[0].split("Z")[0]
    if "." in text:
        head, frac = text.split(".", 1)
        frac = "".join(ch for ch in frac if ch.isdigit())[:6].ljust(6, "0")
        text = f"{head}.{frac}"
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def window_for(created_at: str | None) -> dict | None:
    ts = parse_ts(created_at)
    if ts is None:
        return None
    for slice_ in SLICES:
        start = parse_ts(slice_["start"])
        end = parse_ts(slice_["end"])
        if start and end and start <= ts < end:
            return slice_
    return None

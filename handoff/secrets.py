"""Refuse to turn a transcript into a sellable task if it looks like secrets.

Investigate for research can still run. Catalog and task export cannot.
This is a stub, not a guarantee that sensitive material is gone.
"""

from __future__ import annotations

import re

PATTERNS = (
    re.compile(r"hf_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S{8,}"),
)


class SecretLeak(ValueError):
    pass


def findings(raw: str) -> list[str]:
    hits = []
    for pat in PATTERNS:
        if pat.search(raw or ""):
            hits.append(pat.pattern)
    return hits


def assert_clean(raw: str) -> None:
    hits = findings(raw)
    if hits:
        raise SecretLeak(
            "This transcript looks like it contains secrets (.env / hf_ / sk- / keys). "
            "Handoff will not build a task or list it. Strip the secret and retry."
        )

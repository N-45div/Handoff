"""Keep secrets out of anything Handoff exports.

A raw chat transcript that looks like it holds secrets is refused. An agent trace is redacted
string by string (tool output often echoes the environment), then the finished task is checked
again. Investigate for research can still run. This is pattern matching, not a guarantee that
sensitive material is gone.
"""

from __future__ import annotations

import re

PATTERNS = (
    re.compile(r"hf_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*(?!\[redacted\])\S{8,}"),
)
PEM_BLOCK = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)")
ASSIGN = re.compile(r"(?i)((?:api[_-]?key|secret|password|token)\s*[:=]\s*)(?!\[redacted\])\S{8,}")


class SecretLeak(ValueError):
    pass


def redact(text: str) -> tuple[str, int]:
    """Replace anything that looks like a secret with [redacted]; return the text and the count."""
    out, count = PEM_BLOCK.subn("[redacted]", text or "")
    for pat in PATTERNS[:-1]:
        out, n = pat.subn("[redacted]", out)
        count += n
    out, n = ASSIGN.subn(lambda m: m.group(1) + "[redacted]", out)
    return out, count + n


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

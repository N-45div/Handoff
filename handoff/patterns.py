"""Heuristic patterns for agent-to-agent promises. Quote must still appear in the message."""

from __future__ import annotations

import re

COMMIT_RE = re.compile(
    r"\b(i(?:['’]?ll| will| can| am going to)|let me|on it|leave it (?:to|with) me|"
    r"i(?:['’]m| am) on (?:it|this)|i(?:['’]ve| have) got (?:it|this))\b",
    re.I,
)
REQUEST_RE = re.compile(
    r"\b(can you|could you|would you|please (?:handle|take|send|do)|"
    r"your (?:job|turn)|you (?:handle|take|do|send))\b",
    re.I,
)
ACCEPT_RE = re.compile(
    r"\b(on it|got it|i(?:['’]ll| will) (?:take|handle|do|send)|leaving it to me)\b",
    re.I,
)
AGENT_MENTION_RE = re.compile(
    r"\b(claude|opus|sonnet|gpt-?\d|gemini|kimi|deepseek|grok|o\d)\b",
    re.I,
)


def looks_like_handoff(text: str) -> bool:
    if not text or len(text) < 12:
        return False
    return bool(COMMIT_RE.search(text) or REQUEST_RE.search(text) or ACCEPT_RE.search(text))

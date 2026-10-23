"""Zetaris Lightning REST — documented POST /sql-editor/sqls/run only."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


def load_env() -> None:
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env.local")
    load_dotenv(root / ".env")
    extra = Path(r"C:\Users\DivijN\zetaris-getting-started\.env.local")
    if extra.is_file():
        load_dotenv(extra, override=False)


def _short(text: str, n: int = 400) -> str:
    return " ".join(text.split())[:n]


def login_token() -> str:
    load_env()
    key = os.environ.get("ZETARIS_API_KEY")
    if key:
        return key
    user = os.environ.get("ZETARIS_USERNAME")
    password = os.environ.get("ZETARIS_PASSWORD")
    if not user or not password:
        raise RuntimeError("Set ZETARIS_API_KEY or ZETARIS_USERNAME + ZETARIS_PASSWORD in .env.local")
    base = os.environ.get("ZETARIS_BASE_URL", "http://localhost:3000").rstrip("/")
    req = Request(
        f"{base}/api/auth/login",
        data=json.dumps({"username": user, "password": password}).encode(),
        headers={"Content-Type": "application/json", "X-Request-ID": str(uuid.uuid4())},
        method="POST",
    )
    with urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode() or "{}")
    token = None
    if isinstance(body, dict):
        token = body.get("idToken") or body.get("token") or body.get("accessToken")
    if not token:
        raise RuntimeError("Zetaris login did not return a token")
    return str(token)


def run_sql(sql: str, limit: int = 200) -> list:
    load_env()
    token = login_token()
    rest = os.environ.get("ZETARIS_REST_URL", "http://localhost:8888/api/v1.0").rstrip("/")
    org = os.environ.get("ZETARIS_ORG_ID", "1")
    body = {"queryId": str(uuid.uuid4()), "sql": sql, "source": "SqlEditor", "limit": limit}
    req = Request(
        f"{rest}/sql-editor/sqls/run",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Org-ID": org,
            "X-Request-ID": str(uuid.uuid4()),
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=600) as resp:
            out = json.loads(resp.read().decode() or "null")
    except HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {_short(e.read().decode(errors='replace'))}") from e
    except (URLError, OSError) as e:
        raise RuntimeError(f"Cannot reach {rest}: {getattr(e, 'reason', e)}") from e
    if isinstance(out, dict):
        return out.get("data") or []
    return []

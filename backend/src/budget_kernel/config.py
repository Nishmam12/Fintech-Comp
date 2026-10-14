"""Environment-driven settings. Secrets come from .env (never committed)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env")

_SCHEMA_RE = re.compile(r"^[a-z_][a-z0-9_]{0,40}$")


@dataclass(frozen=True)
class Settings:
    database_url: str
    schema: str
    test_schema: str

    @staticmethod
    def load() -> "Settings":
        url = os.environ.get("DATABASE_URL", "")
        if not url or "[YOUR-PASSWORD]" in url:
            raise RuntimeError("DATABASE_URL is not set in .env")
        s = Settings(
            database_url=url,
            schema=os.environ.get("BK_SCHEMA", "bk"),
            test_schema=os.environ.get("BK_TEST_SCHEMA", "bk_test"),
        )
        for name in (s.schema, s.test_schema):
            if not _SCHEMA_RE.match(name):
                raise RuntimeError(f"invalid schema name: {name!r}")
        return s

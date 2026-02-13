"""EPACK Postgres store (optional).

V9 fix: zero import-time side effects.

This store is intentionally minimal. Importing this module never tries to
connect to Postgres.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

try:
    import psycopg2  # type: ignore
except Exception:  # pragma: no cover
    psycopg2 = None


class PostgresStoreConfigError(RuntimeError):
    pass


@dataclass
class PostgresEpackStore:
    database_url: Optional[str] = None
    connect_timeout_s: int = 5

    def _url(self) -> str:
        url = self.database_url or os.getenv("DATABASE_URL")
        if not url:
            raise PostgresStoreConfigError(
                "DATABASE_URL is not set. Configure Postgres or use a non-Postgres EPACK store."
            )
        return url

    def connect(self):
        if psycopg2 is None:
            raise PostgresStoreConfigError(
                "psycopg2 is not installed. Install extras: pip install beaconwise[postgres]"
            )
        return psycopg2.connect(self._url(), connect_timeout=self.connect_timeout_s)

    def write_events(self, events: List[Dict[str, Any]]) -> int:
        """Insert a list of EPACK event dicts. Returns number written."""
        if not events:
            return 0
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS epack_events (
                      id BIGSERIAL PRIMARY KEY,
                      session_id TEXT NOT NULL,
                      event_type TEXT NOT NULL,
                      payload JSONB NOT NULL,
                      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                for ev in events:
                    cur.execute(
                        "INSERT INTO epack_events (session_id, event_type, payload) VALUES (%s,%s,%s)",
                        (ev.get("session_id", ""), ev.get("event_type", ""), json.dumps(ev)),
                    )
        return len(events)

    def iter_events(self, session_id: str, limit: int = 1000) -> Iterable[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM epack_events WHERE session_id=%s ORDER BY id ASC LIMIT %s",
                    (session_id, limit),
                )
                for (payload,) in cur.fetchall():
                    yield payload

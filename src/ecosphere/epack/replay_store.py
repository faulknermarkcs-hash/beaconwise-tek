"""
SQLite-backed EPACK store for fully replayable evidence.

- append(event) writes immutable JSON
- read_all() returns ordered events
- get_by_key(key) convenience for citation cache (type=citation_cache)

Set EPACK_DB_PATH to enable persistence.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import json
import os
import sqlite3
import threading
import time

class SQLiteEpackStore:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS epack_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    key TEXT,
                    payload TEXT NOT NULL
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_epack_type ON epack_events(type)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_epack_key ON epack_events(key)")
            con.commit()

    def append(self, event: Dict[str, Any]) -> None:
        ts = int(event.get("ts") or time.time())
        etype = str(event.get("type") or "event")
        key = event.get("key")
        payload = json.dumps(event, sort_keys=True, default=str)
        with self._lock, sqlite3.connect(self.path) as con:
            con.execute(
                "INSERT INTO epack_events(ts, type, key, payload) VALUES (?,?,?,?)",
                (ts, etype, key, payload),
            )
            con.commit()

    def read_all(self) -> List[Dict[str, Any]]:
        with self._lock, sqlite3.connect(self.path) as con:
            rows = con.execute("SELECT payload FROM epack_events ORDER BY id ASC").fetchall()
        return [json.loads(r[0]) for r in rows]

    def get_by_key(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock, sqlite3.connect(self.path) as con:
            row = con.execute(
                "SELECT payload FROM epack_events WHERE type='citation_cache' AND key=? ORDER BY id DESC LIMIT 1",
                (key,),
            ).fetchone()
        return json.loads(row[0]) if row else None

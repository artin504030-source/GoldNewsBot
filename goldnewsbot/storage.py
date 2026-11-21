"""SQLite persistence adapter with basic durability and health checks."""
from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLiteNewsRepository:
    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)
        if str(self.database_path) != ":memory:":
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS processed_news ("
                "fingerprint TEXT PRIMARY KEY, "
                "processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )

    def check(self) -> bool:
        with self._connect() as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError("Database integrity check failed")
        return True

    def has_seen(self, fingerprint: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM processed_news WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
        return row is not None

    def mark_seen(self, fingerprint: str) -> None:
        if not fingerprint:
            raise ValueError("fingerprint cannot be empty")
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO processed_news (fingerprint) VALUES (?)",
                (fingerprint,),
            )

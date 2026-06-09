from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def from_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


@dataclass(slots=True)
class Artifact:
    id: str
    title: str
    kind: str
    content: Any
    created_at: datetime
    expires_at: datetime
    metadata: dict[str, Any]

    @property
    def expired(self) -> bool:
        return self.expires_at <= utc_now()


class ArtifactStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_expires_at ON artifacts(expires_at)")
            conn.commit()

    def create(self, *, title: str, kind: str, content: Any, ttl_minutes: int, metadata: dict[str, Any] | None = None) -> Artifact:
        artifact_id = uuid4().hex[:12]
        now = utc_now()
        expires_at = now + timedelta(minutes=ttl_minutes)
        payload = json.dumps(content, ensure_ascii=False)
        meta = json.dumps(metadata or {}, ensure_ascii=False)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO artifacts (id, title, kind, content_json, metadata_json, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (artifact_id, title, kind, payload, meta, to_iso(now), to_iso(expires_at)),
            )
            conn.commit()
        return Artifact(artifact_id, title, kind, content, now, expires_at, metadata or {})

    def _row_to_artifact(self, row: sqlite3.Row) -> Artifact:
        return Artifact(
            id=row["id"],
            title=row["title"],
            kind=row["kind"],
            content=json.loads(row["content_json"]),
            metadata=json.loads(row["metadata_json"]),
            created_at=from_iso(row["created_at"]),
            expires_at=from_iso(row["expires_at"]),
        )

    def get(self, artifact_id: str) -> Artifact | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
        if row is None:
            return None
        artifact = self._row_to_artifact(row)
        if artifact.expired:
            self.delete(artifact_id)
            return None
        return artifact

    def list_recent(self, limit: int = 6) -> list[Artifact]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE expires_at > ? ORDER BY created_at DESC LIMIT ?",
                (to_iso(utc_now()), limit),
            ).fetchall()
        return [self._row_to_artifact(row) for row in rows]

    def delete(self, artifact_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
            conn.commit()

    def cleanup_expired(self) -> int:
        now_iso = to_iso(utc_now())
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM artifacts WHERE expires_at <= ?", (now_iso,))
            conn.commit()
            return cur.rowcount

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM artifacts").fetchone()
            return int(row["n"]) if row else 0

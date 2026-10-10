"""Crash-tolerant run outcomes and synthetic replay records.

Default mode saves only redacted/hashes, never raw prompts. Explicit fixture
recording is for synthetic test tasks only; opt-in is mandatory.
"""

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentx.guard.policy import redact
from agentx.llm.cassette import request_fingerprint


class ReplayDriftError(LookupError):
    """Recorded requests no longer match the exact replay transcript."""


class RunStore:
    def __init__(self, path: Path, *, allow_synthetic_replay: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.allow_synthetic_replay = allow_synthetic_replay
        self._lock = threading.Lock()
        with self._connection() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute(
                "CREATE TABLE IF NOT EXISTS runs ("
                "run_id TEXT PRIMARY KEY, status TEXT NOT NULL, "
                "updated_utc TEXT NOT NULL, safe_payload TEXT NOT NULL)"
            )
            c.execute(
                "CREATE TABLE IF NOT EXISTS responses ("
                "run_id TEXT NOT NULL, index_no INTEGER NOT NULL, "
                "request_hash TEXT NOT NULL, response TEXT NOT NULL, "
                "PRIMARY KEY(run_id,index_no))"
            )

    def _connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def save(self, run_id: str, status: str, payload: dict[str, Any]) -> None:
        safe = redact(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))
        if len(safe) > 4096:
            safe = safe[:4096] + " [truncated]"
        with self._lock, self._connection() as c:
            c.execute(
                """INSERT INTO runs (run_id,status,updated_utc,safe_payload)
                   VALUES (?,?,?,?)
                   ON CONFLICT(run_id) DO UPDATE SET
                   status=excluded.status,
                   updated_utc=excluded.updated_utc,
                   safe_payload=excluded.safe_payload""",
                (run_id, status, datetime.now(UTC).isoformat(), safe),
            )

    def load(self, run_id: str) -> dict[str, Any] | None:
        with self._connection() as c:
            item = c.execute(
                "SELECT status,safe_payload,updated_utc FROM runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
        if item is None:
            return None
        return {"status": item[0], "safe_payload": item[1], "updated_utc": item[2]}

    def record_synthetic(
        self,
        run_id: str,
        index: int,
        request: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        if not self.allow_synthetic_replay:
            raise PermissionError("raw synthetic replay recording requires explicit opt-in")
        fingerprint = request_fingerprint(request)
        data = json.dumps(response, ensure_ascii=False, sort_keys=True, allow_nan=False)
        with self._lock, self._connection() as c:
            c.execute(
                "INSERT INTO responses (run_id,index_no,request_hash,response) VALUES (?,?,?,?)",
                (run_id, index, fingerprint, data),
            )

    def replay_synthetic(self, run_id: str, index: int, request: dict[str, Any]) -> dict[str, Any]:
        if not self.allow_synthetic_replay:
            raise PermissionError("raw synthetic replay requires explicit opt-in")
        with self._connection() as c:
            item = c.execute(
                "SELECT request_hash,response FROM responses WHERE run_id=? AND index_no=?",
                (run_id, index),
            ).fetchone()
        if item is None or item[0] != request_fingerprint(request):
            raise ReplayDriftError(f"cassette drift at response index {index}; no live fallback")
        result: dict[str, Any] = json.loads(item[1])
        return result

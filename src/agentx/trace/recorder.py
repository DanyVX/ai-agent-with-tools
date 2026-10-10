"""Append-only JSONL spans. Payloads are redacted and truncated before persistence."""

import hashlib
import json
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from agentx.guard.policy import redact


def safe_preview(value: Any, limit: int = 512) -> dict[str, str]:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    safe = redact(serialized)
    return {
        "preview": safe[:limit] + (" [truncated]" if len(safe) > limit else ""),
        "sha256": hashlib.sha256(serialized.encode()).hexdigest(),
    }


class TraceRecorder:
    """One writer lock per instance; filesystem append + flush per span."""

    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def emit(
        self,
        name: str,
        *,
        parent: str | None = None,
        status: str = "ok",
        elapsed_ns: int = 0,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "span_id": hashlib.sha256(
                f"{self.run_id}:{name}:{time.monotonic_ns()}".encode()
            ).hexdigest()[:16],
            "run_id": self.run_id,
            "parent_span_id": parent,
            "name": name,
            "status": status,
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "elapsed_ns": max(0, elapsed_ns),
            "attributes": safe_preview(attributes or {}),
        }
        with self._lock:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()

    @contextmanager
    def span(
        self, name: str, *, attributes: dict[str, Any] | None = None
    ) -> Iterator[None]:
        start = time.monotonic_ns()
        try:
            yield
        except Exception:
            self.emit(
                name, status="error", elapsed_ns=time.monotonic_ns() - start,
                attributes=attributes,
            )
            raise
        else:
            self.emit(
                name, elapsed_ns=time.monotonic_ns() - start, attributes=attributes
            )

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

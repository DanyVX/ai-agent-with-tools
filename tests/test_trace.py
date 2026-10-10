"""Trace redaction and replay drift tests."""

from pathlib import Path

import pytest

from agentx.runs.store import ReplayDriftError, RunStore
from agentx.trace.recorder import TraceRecorder


def test_redacted_trace(tmp_path: Path) -> None:
    trace = TraceRecorder(tmp_path / "trace.jsonl", "synthetic-run")
    with trace.span("llm", attributes={"prompt": "token=secretvalue user@example.com"}):
        pass
    records = trace.records()
    assert records[0]["elapsed_ns"] >= 0
    saved = (tmp_path / "trace.jsonl").read_text(encoding="utf-8")
    assert "secretvalue" not in saved
    assert "user@example.com" not in saved


def test_run_store_safe_default(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.sqlite3")
    store.save("r", "running", {"task": "Contact alice@example.com"})
    loaded = store.load("r")
    assert loaded is not None and "alice@example.com" not in loaded["safe_payload"]
    with pytest.raises(PermissionError):
        store.record_synthetic("r", 0, {"a": 1}, {"answer": "yes"})


def test_replay_exact_match_and_drift(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.sqlite3", allow_synthetic_replay=True)
    request = {"messages": [{"role": "user", "content": "synthetic"}]}
    store.record_synthetic("r", 0, request, {"text": "done"})
    assert store.replay_synthetic("r", 0, request)["text"] == "done"
    with pytest.raises(ReplayDriftError):
        store.replay_synthetic("r", 0, {"messages": []})


def test_trace_large_payload_truncated(tmp_path: Path) -> None:
    trace = TraceRecorder(tmp_path / "trace.jsonl", "r")
    trace.emit("tool", attributes={"body": "x" * 10_000})
    assert "[truncated]" in trace.records()[0]["attributes"]["preview"]

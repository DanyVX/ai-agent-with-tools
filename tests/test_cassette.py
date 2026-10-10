"""Replay cannot silently contact a provider when a fixture drifts."""

import json
from pathlib import Path

import pytest

from agentx.llm.cassette import (
    CassetteInvalid,
    CassetteMiss,
    CassetteStore,
    request_fingerprint,
)


def test_replay_unicode_json(tmp_path: Path) -> None:
    request = {"tools": [], "messages": [{"role": "user", "content": "Hi 👋 مرحبا"}]}
    digest = request_fingerprint(request)
    (tmp_path / f"{digest}.json").write_text(
        json.dumps({"request_hash": digest, "response": {"text": "Ready ✅"}}),
        encoding="utf-8",
    )
    assert CassetteStore(tmp_path).replay(request)["text"] == "Ready ✅"


def test_canonical_order() -> None:
    assert request_fingerprint({"a": 1, "b": 2}) == request_fingerprint({"b": 2, "a": 1})


def test_mismatch_fails_without_network(tmp_path: Path) -> None:
    with pytest.raises(CassetteMiss, match="NOT sent"):
        CassetteStore(tmp_path).replay({"messages": ["changed prompt"]})


def test_corrupt_or_forged_cassette_rejected(tmp_path: Path) -> None:
    request = {"a": 1}
    path = tmp_path / f"{request_fingerprint(request)}.json"
    path.write_text('{"request_hash": "forged", "response": {}}', encoding="utf-8")
    with pytest.raises(CassetteInvalid, match="fingerprint mismatch"):
        CassetteStore(tmp_path).replay(request)
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(CassetteInvalid, match="cannot be loaded"):
        CassetteStore(tmp_path).replay(request)


@pytest.mark.parametrize("payload", [{"a": float("nan")}, {"a": object()}])
def test_non_json_request_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(CassetteInvalid, match="canonical JSON"):
        request_fingerprint(payload)

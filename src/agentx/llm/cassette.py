"""Offline-only replay with a canonical request fingerprint.

Fixtures are created by deliberate review, never automatically recorded from
live prompts. Unknown or drifted requests fail rather than going online.
"""

import hashlib
import json
from pathlib import Path
from typing import Any


class CassetteMiss(LookupError):
    """No reviewed offline fixture matched the request."""


class CassetteInvalid(ValueError):
    """Fixture is invalid or does not match its key."""


def request_fingerprint(request: dict[str, Any]) -> str:
    try:
        raw = json.dumps(
            request, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CassetteInvalid("Request is not canonical JSON") from exc
    return hashlib.sha256(raw).hexdigest()


class CassetteStore:
    def __init__(self, root: Path):
        self.root = root

    def replay(self, request: dict[str, Any]) -> dict[str, Any]:
        digest = request_fingerprint(request)
        file = self.root / f"{digest}.json"
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CassetteMiss(
                f"No cassette matches request hash {digest}. "
                "The request was NOT sent to a provider; review fixture drift."
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise CassetteInvalid(f"Cassette {digest} cannot be loaded") from exc
        if not isinstance(data, dict) or data.get("request_hash") != digest:
            raise CassetteInvalid(f"Cassette {digest} fingerprint mismatch")
        response = data.get("response")
        if not isinstance(response, dict):
            raise CassetteInvalid(f"Cassette {digest} must have an object response")
        return response

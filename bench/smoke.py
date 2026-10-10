"""M0 microbenchmark: offline cassette hashing only; not an agent performance claim."""

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Benchmark is intentionally runnable from a source checkout after installation.
from agentx.llm.cassette import request_fingerprint


def commit_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown (source not in git checkout)"


def main() -> None:
    loops = 100
    request = {"messages": [{"role": "user", "content": "synthetic smoke benchmark"}]}
    start = time.perf_counter_ns()
    hashes = [request_fingerprint(request) for _ in range(loops)]
    elapsed = time.perf_counter_ns() - start
    assert len(set(hashes)) == 1
    result = {
        "benchmark": "m0_cassette_fingerprint_smoke",
        "not_an_agent_success_metric": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit_sha(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("pydantic", "pydantic-settings", "httpx")
        },
        "iterations": loops,
        "elapsed_ns": elapsed,
        "sample_sha256": hashlib.sha256(hashes[0].encode()).hexdigest(),
    }
    output = Path("results/m0-smoke.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output} (local hardware and commit recorded)")


if __name__ == "__main__":
    main()

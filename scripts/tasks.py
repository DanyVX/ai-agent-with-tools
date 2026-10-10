"""Cross-platform developer tasks; Makefile delegates here."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "task",
        choices=[
            "setup",
            "lint",
            "format",
            "typecheck",
            "test",
            "test-fast",
            "bench",
            "run",
            "docker-build",
            "clean",
        ],
    )
    task = parser.parse_args().task
    commands = {
        "setup": [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
        "lint": [sys.executable, "-m", "ruff", "check", "."],
        "format": [sys.executable, "-m", "ruff", "format", "."],
        "typecheck": [sys.executable, "-m", "mypy", "src/agentx"],
        "test": [sys.executable, "-m", "pytest", "-m", "not slow and not gpu"],
        "test-fast": [sys.executable, "-m", "pytest", "-m", "not slow and not gpu"],
        "bench": [sys.executable, "bench/smoke.py"],
        "run": [sys.executable, "-m", "agentx.cli", "doctor"],
    }
    if task == "clean":
        for name in (".pytest_cache", ".mypy_cache", ".ruff_cache", "htmlcov"):
            shutil.rmtree(ROOT / name, ignore_errors=True)
        return
    if task == "docker-build":
        if not (ROOT / "Dockerfile").exists():
            parser.exit(2, "Docker image is not part of M0 (no Dockerfile).\n")
        commands["docker-build"] = ["docker", "build", "-t", "agentx:local", "."]
    subprocess.run(commands[task], cwd=ROOT, check=True)  # noqa: S603 - fixed allowlist


if __name__ == "__main__":
    main()

"""Deterministic synthetic sandbox created from the installed agentx package."""

import sqlite3
from contextlib import closing
from pathlib import Path


def bootstrap(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "welcome.txt").write_text("Project AgentX synthetic sandbox.\n", encoding="utf-8")
    path = root / "sample.sqlite3"
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("DELETE FROM products")
        connection.executemany(
            "INSERT INTO products (id, name) VALUES (?, ?)",
            [(1, "synthetic pencil"), (2, "synthetic notebook"), (3, "synthetic lamp")],
        )

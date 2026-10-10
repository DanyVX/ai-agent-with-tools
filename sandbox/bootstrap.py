"""Populate deterministic synthetic sample data, never real customer records."""

import sqlite3
from pathlib import Path


def bootstrap(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "welcome.txt").write_text("Project AgentX synthetic sandbox.\n", encoding="utf-8")
    db = root / "sample.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("DELETE FROM products")
        connection.executemany(
            "INSERT INTO products (id, name) VALUES (?, ?)",
            [(1, "synthetic pencil"), (2, "synthetic notebook"), (3, "synthetic lamp")],
        )


if __name__ == "__main__":
    bootstrap(Path("sandbox/data"))

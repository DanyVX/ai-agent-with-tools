"""Offline confinement and tool contract tests."""

import asyncio
import sqlite3
from pathlib import Path

import pytest

from agentx.tools.builtins import CalculatorArgs, calculate, confined, make_registry
from agentx.tools.core import Tool, ToolRegistry


@pytest.mark.parametrize(
    "path",
    ["../secret", "/etc/passwd", "C:\\Windows\\test", "..%2Fetc", "sub\\..\\x", "a\x00b"],
)
def test_sandbox_escape_rejected(tmp_path: Path, path: str) -> None:
    with pytest.raises(ValueError):
        confined(tmp_path, path)


def test_symlink_escape_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-file.txt"
    outside.write_text("no", encoding="utf-8")
    (tmp_path / "link").symlink_to(outside)
    with pytest.raises(ValueError):
        confined(tmp_path, "link")


@pytest.mark.parametrize("expr", ["__import__('os')", "2**100", "1/0", "(1).__class__"])
def test_calculator_rejects_unsafe_expression(expr: str) -> None:
    with pytest.raises((ValueError, SyntaxError, ArithmeticError)):
        calculate(expr)


def test_calculator_arithmetic() -> None:
    assert calculate("4*(3+2)") == "20"


@pytest.mark.asyncio
async def test_registry_schema_unknown_args_and_approval(tmp_path: Path) -> None:
    reg = make_registry(tmp_path)
    assert len(reg.specs()) == 8
    unknown = await reg.execute("missing", {}, call_id="1")
    assert unknown.code == "unknown_tool"
    invalid = await reg.execute("calculator", {"expression": "2+2", "extra": 1}, call_id="2")
    assert invalid.code == "invalid_arguments"
    denied = await reg.execute(
        "write_note", {"filename": "a", "content": "b", "idempotency_key": "abc123"},
        call_id="3",
    )
    assert denied.code == "approval_required"


@pytest.mark.asyncio
async def test_note_idempotent(tmp_path: Path) -> None:
    reg = make_registry(tmp_path)
    data = {"filename": "todo", "content": "yes", "idempotency_key": "note123"}
    first = await reg.execute("write_note", data, call_id="a", approved=True)
    second = await reg.execute("write_note", data, call_id="b", approved=True)
    assert first.ok and second.ok
    assert len(list((tmp_path / "notes").iterdir())) == 1


@pytest.mark.asyncio
async def test_http_get_offline_allowlist(tmp_path: Path) -> None:
    reg = make_registry(
        tmp_path, allowed_hosts={"example.org"},
        web_fixtures={"https://example.org/a": "synthetic page"},
    )
    ok = await reg.execute("http_get", {"url": "https://example.org/a"}, call_id="a")
    denied = await reg.execute("http_get", {"url": "https://127.0.0.1/"}, call_id="b")
    absent = await reg.execute("http_get", {"url": "https://example.org/b"}, call_id="c")
    assert ok.ok and denied.code == "tool_error" and absent.code == "tool_error"


@pytest.mark.asyncio
async def test_sql_is_read_only(tmp_path: Path) -> None:
    with sqlite3.connect(tmp_path / "sample.sqlite3") as c:
        c.execute("CREATE TABLE items (id INTEGER)")
        c.execute("INSERT INTO items VALUES (10)")
    reg = make_registry(tmp_path)
    ok = await reg.execute("sql_query", {"query": "SELECT id FROM items"}, call_id="1")
    bad = await reg.execute("sql_query", {"query": "DELETE FROM items"}, call_id="2")
    assert ok.ok and "10" in ok.output and bad.code == "tool_error"


@pytest.mark.asyncio
async def test_parallel_preserves_order(tmp_path: Path) -> None:
    reg = make_registry(tmp_path)
    calls = [
        ("calculator", {"expression": "1+1"}, "a"),
        ("calculator", {"expression": "2+2"}, "b"),
    ]
    outputs = await reg.execute_many(calls, allowed={"calculator"})
    assert [o.call_id for o in outputs] == ["a", "b"]
    assert '"2"' in outputs[0].output and '"4"' in outputs[1].output


@pytest.mark.asyncio
async def test_tool_timeout_and_duplicate(tmp_path: Path) -> None:
    reg = ToolRegistry()

    async def hang(_arg: CalculatorArgs) -> str:
        await asyncio.sleep(1)
        return "unexpected"

    tool = Tool("hang", "test", CalculatorArgs, hang, timeout_s=0.01)
    reg.register(tool)
    with pytest.raises(ValueError, match="duplicate"):
        reg.register(tool)
    res = await reg.execute("hang", {"expression": "1"}, call_id="a")
    assert res.code == "timeout"

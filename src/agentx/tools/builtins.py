"""Built-in tools constrained to synthetic fixtures and sandbox filesystem."""

import ast
import ipaddress
import json
import operator
import re
import sqlite3
from collections.abc import Awaitable, Callable
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from pydantic import Field

from agentx.tools.core import StrictArgs, Tool, ToolRegistry


class CalculatorArgs(StrictArgs):
    expression: str = Field(min_length=1, max_length=160)


class PathArgs(StrictArgs):
    path: str = Field(min_length=1, max_length=260)


class SearchArgs(StrictArgs):
    term: str = Field(min_length=1, max_length=80)


class HttpArgs(StrictArgs):
    url: str = Field(min_length=12, max_length=2048)


class SQLArgs(StrictArgs):
    query: str = Field(min_length=1, max_length=1000)


class NoteArgs(StrictArgs):
    filename: str = Field(min_length=1, max_length=60)
    content: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(pattern=r"^[a-zA-Z0-9_-]{6,64}$")


class EmailArgs(StrictArgs):
    to: str = Field(min_length=3, max_length=120)
    subject: str = Field(min_length=1, max_length=150)
    body: str = Field(min_length=1, max_length=3000)
    idempotency_key: str = Field(pattern=r"^[a-zA-Z0-9_-]{6,64}$")


_ALLOWED_OPERATORS: dict[type[ast.operator], Callable[[Decimal, Decimal], Decimal]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def calculate(expression: str) -> str:
    tree = ast.parse(expression, mode="eval")
    if len(list(ast.walk(tree))) > 35:
        raise ValueError("expression too complex")

    def visit(node: ast.AST, depth: int = 0) -> Decimal:
        if depth > 12:
            raise ValueError("expression too deep")
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return Decimal(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand, depth + 1)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
            left = visit(node.left, depth + 1)
            right = visit(node.right, depth + 1)
            if isinstance(node.op, ast.Div) and right == 0:
                raise ValueError("division by zero")
            value = _ALLOWED_OPERATORS[type(node.op)](left, right)
            if value.adjusted() > 30:
                raise ValueError("result too large")
            return value
        raise ValueError("unsupported mathematical syntax")

    return str(visit(tree.body))


def confined(root: Path, name: str) -> Path:
    """Normalize only after rejecting ambiguous paths and encoded traversal."""
    if (
        not name
        or "\x00" in name
        or "\\" in name
        or "%" in name
        or Path(name).is_absolute()
        or ".." in Path(name).parts
        or ":" in name
        or unquote(name) != name
    ):
        raise ValueError("unsafe path")
    safe_root = root.resolve()
    try:
        resolved = (safe_root / name).resolve(strict=False)
        resolved.relative_to(safe_root)
    except (ValueError, RuntimeError, OSError) as exc:
        raise ValueError("path escapes sandbox") from exc
    return resolved


def _safe_url(url: str, allowlist: set[str]) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or parsed.fragment
    ):
        raise ValueError("invalid or non-HTTPS URL")
    host = parsed.hostname.rstrip(".").lower()
    if host not in allowlist:
        raise ValueError("host is not allowlisted")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not ip.is_global:
            raise ValueError("private, loopback and reserved addresses forbidden")
    return url


def make_registry(
    sandbox: Path,
    *,
    allowed_hosts: set[str] | None = None,
    web_fixtures: dict[str, str] | None = None,
) -> ToolRegistry:
    """Build tool handlers; HTTP fixtures only (no DNS/rebinding exposure)."""
    root = sandbox.resolve()
    root.mkdir(parents=True, exist_ok=True)
    hosts = {h.lower() for h in (allowed_hosts or {"example.org"})}
    pages = web_fixtures or {}
    registry = ToolRegistry()

    async def calculator(arg: StrictArgs) -> Any:
        assert isinstance(arg, CalculatorArgs)
        return {"value": calculate(arg.expression)}

    async def read_file(arg: StrictArgs) -> Any:
        assert isinstance(arg, PathArgs)
        path = confined(root, arg.path)
        if not path.is_file():
            raise ValueError("not a regular file")
        if path.stat().st_size > 65536:
            raise ValueError("file too large")
        return {"content": path.read_text(encoding="utf-8")}

    async def list_dir(arg: StrictArgs) -> Any:
        assert isinstance(arg, PathArgs)
        path = confined(root, arg.path)
        if not path.is_dir():
            raise ValueError("not a directory")
        return {"entries": sorted(p.name for p in path.iterdir())[:100]}

    async def search_files(arg: StrictArgs) -> Any:
        assert isinstance(arg, SearchArgs)
        matches: list[str] = []
        for path in root.rglob("*"):
            if len(matches) >= 50:
                break
            if path.is_symlink() or not path.is_file():
                continue
            if path.stat().st_size <= 65536:
                try:
                    if arg.term.casefold() in path.read_text(encoding="utf-8").casefold():
                        matches.append(str(path.relative_to(root)))
                except (UnicodeError, OSError):
                    continue
        return {"paths": matches}

    async def http_get(arg: StrictArgs) -> Any:
        assert isinstance(arg, HttpArgs)
        url = _safe_url(arg.url, hosts)
        if url not in pages:
            raise ValueError("no reviewed HTTP fixture; live requests are disabled")
        return {"url": url, "body": pages[url], "source": "offline_fixture"}

    async def sql_query(arg: StrictArgs) -> Any:
        assert isinstance(arg, SQLArgs)
        q = arg.query.strip()
        if not re.match(r"^SELECT\s", q, flags=re.IGNORECASE):
            raise ValueError("only SELECT queries allowed")
        if ";" in q or "--" in q or "/*" in q:
            raise ValueError("multiple statements and comments forbidden")
        db = root / "sample.sqlite3"
        if not db.is_file():
            raise ValueError("sample database missing")
        uri = f"file:{db.as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=2) as connection:
            connection.execute("PRAGMA query_only=ON")
            cursor = connection.execute(q)
            rows = cursor.fetchmany(101)
            if len(rows) > 100:
                raise ValueError("query exceeds 100 rows")
            return {"columns": [col[0] for col in cursor.description], "rows": rows}

    async def _write_once(folder: str, key: str, contents: dict[str, Any]) -> Any:
        dest = root / folder
        dest.mkdir(parents=True, exist_ok=True)
        path = confined(root, f"{folder}/{key}.json")
        data = json.dumps(contents, ensure_ascii=False, sort_keys=True)
        try:
            with path.open("x", encoding="utf-8") as file:
                file.write(data)
            return {"record_id": key, "created": True}
        except FileExistsError as exc:
            if path.read_text(encoding="utf-8") != data:
                raise ValueError("idempotency key collision") from exc
            return {"record_id": key, "created": False}

    async def write_note(arg: StrictArgs) -> Any:
        assert isinstance(arg, NoteArgs)
        name = confined(root, arg.filename).name
        if name != arg.filename:
            raise ValueError("unsafe filename")
        return await _write_once(
            "notes", arg.idempotency_key, {"filename": name, "content": arg.content}
        )

    async def send_email_mock(arg: StrictArgs) -> Any:
        assert isinstance(arg, EmailArgs)
        if "@" not in arg.to:
            raise ValueError("invalid recipient")
        return await _write_once(
            "outbox",
            arg.idempotency_key,
            {"to": arg.to, "subject": arg.subject, "body": arg.body, "mock": True},
        )

    definitions: list[
        tuple[str, str, type[StrictArgs], Callable[[StrictArgs], Awaitable[Any]], bool]
    ] = [
        (
            "calculator",
            "Safely evaluate + - * / and parentheses",
            CalculatorArgs,
            calculator,
            False,
        ),
        ("read_file", "Read a UTF-8 file under sandbox root", PathArgs, read_file, False),
        ("list_dir", "List a sandbox directory", PathArgs, list_dir, False),
        ("search_files", "Find text in sandbox files", SearchArgs, search_files, False),
        ("http_get", "Retrieve reviewed offline HTTPS fixture", HttpArgs, http_get, False),
        ("sql_query", "Read-only SELECT on synthetic sample SQLite DB", SQLArgs, sql_query, False),
        ("write_note", "Create an approved, idempotent sandbox note", NoteArgs, write_note, True),
        (
            "send_email_mock",
            "Create approved mock outbox entry, never sends",
            EmailArgs,
            send_email_mock,
            True,
        ),
    ]
    for name, description, model, handler, effect in definitions:
        registry.register(
            Tool(
                name=name,
                description=description,
                arguments=model,
                handler=handler,
                side_effect=effect,
                timeout_s=5,
                max_output_chars=4096,
            )
        )
    return registry

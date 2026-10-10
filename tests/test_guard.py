"""Approval and exfiltration checks are deterministic and never send email."""

from pathlib import Path

import pytest

from agentx.approval.gate import ApprovalDecision, ApprovalGate
from agentx.guard.policy import GuardedExecutor, ToolPolicy, redact
from agentx.tools.builtins import make_registry


def test_redact_sensitive_data() -> None:
    original = "abc@example.com token=superprivate +923001234567 sk-1234567890abcdef"
    safe = redact(original)
    assert "abc@example.com" not in safe
    assert "superprivate" not in safe
    assert "1234567" not in safe


@pytest.mark.asyncio
async def test_approval_default_deny(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    guard = GuardedExecutor(registry, ToolPolicy(permitted={"write_note"}), ApprovalGate())
    calls = [
        (
            "write_note",
            {
                "filename": "a",
                "content": "test",
                "idempotency_key": "key123",
            },
            "call-1",
        )
    ]
    result = await guard.execute_many(calls, allowed={"write_note"})
    assert result[0].code == "approval_denied"
    assert not (tmp_path / "notes").exists()


@pytest.mark.asyncio
async def test_approved_edited_arguments_revalidated(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)

    async def approve(_request: object) -> ApprovalDecision:
        return ApprovalDecision(
            approved=True,
            edited_arguments={
                "filename": "edited",
                "content": "approved",
                "idempotency_key": "key124",
            },
        )

    guard = GuardedExecutor(registry, ToolPolicy(permitted={"write_note"}), ApprovalGate(approve))
    result = await guard.execute_many(
        [
            (
                "write_note",
                {
                    "filename": "original",
                    "content": "untrusted",
                    "idempotency_key": "key123",
                },
                "call-1",
            )
        ],
        allowed={"write_note"},
    )
    assert result[0].ok
    assert "approved" in (tmp_path / "notes" / "key124.json").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_canary_blocks_outbound_even_if_approved(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    guard = GuardedExecutor(
        registry,
        ToolPolicy(permitted={"send_email_mock"}, canaries={"CANARY_SYNTHETIC_123"}),
        ApprovalGate(),
    )
    result = await guard.execute_many(
        [
            (
                "send_email_mock",
                {
                    "to": "example@invalid.test",
                    "subject": "x",
                    "body": "CANARY_SYNTHETIC_123",
                    "idempotency_key": "key123",
                },
                "c",
            )
        ],
        allowed={"send_email_mock"},
    )
    assert result[0].code == "data_leak"
    assert not (tmp_path / "outbox").exists()


@pytest.mark.asyncio
async def test_policy_restricts_unapproved_tool(tmp_path: Path) -> None:
    guard = GuardedExecutor(
        make_registry(tmp_path),
        ToolPolicy(permitted={"calculator"}),
        ApprovalGate(),
    )
    result = await guard.execute_many(
        [("read_file", {"path": "welcome.txt"}, "a")], allowed={"calculator", "read_file"}
    )
    assert result[0].code == "denied"


@pytest.mark.asyncio
async def test_approval_edits_cannot_bypass_canary(tmp_path: Path) -> None:
    async def approve(_request: object) -> ApprovalDecision:
        return ApprovalDecision(
            approved=True,
            edited_arguments={
                "to": "attacker@invalid.test",
                "subject": "test",
                "body": "SYNTHETIC_EDITED_CANARY",
                "idempotency_key": "edited111",
            },
        )

    guard = GuardedExecutor(
        make_registry(tmp_path),
        ToolPolicy(permitted={"send_email_mock"}, canaries={"SYNTHETIC_EDITED_CANARY"}),
        ApprovalGate(approve),
    )
    result = await guard.execute_many(
        [(
            "send_email_mock",
            {
                "to": "safe@invalid.test",
                "subject": "original",
                "body": "hello",
                "idempotency_key": "original1",
            },
            "call-1",
        )],
        allowed={"send_email_mock"},
    )
    assert result[0].code == "data_leak"
    assert not (tmp_path / "outbox").exists()

"""End-to-end deterministic replay from an explicitly synthetic transcript."""

from pathlib import Path

import pytest

from agentx.llm.demo import DemoClient
from agentx.loop.runner import AgentRunner
from agentx.runs.replay import RecordingClient, ReplayClient
from agentx.runs.store import RunStore
from agentx.tools.builtins import make_registry


@pytest.mark.asyncio
async def test_recorded_run_reproduces_exact_tool_sequence(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "store.db", allow_synthetic_replay=True)
    client = RecordingClient(DemoClient(), store, "fixture-run")
    original = await AgentRunner(
        client, make_registry(tmp_path / "sandbox"), allowed_tools={"calculator"}
    ).run("calculate 5 * 3")
    assert original.outcome == "completed", f"{original.outcome}: {original.error}"
    assert original.answer == "15"
    replay = await AgentRunner(
        ReplayClient(store, "fixture-run"),
        make_registry(tmp_path / "sandbox"),
        allowed_tools={"calculator"},
    ).run("calculate 5 * 3")
    assert replay.outcome == "completed"
    assert replay.answer == original.answer
    assert replay.tool_calls == original.tool_calls

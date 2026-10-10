"""User CLI: offline scripted demos by default, explicit opt-in for paid providers."""

import asyncio
import json
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx
import typer
from pydantic import ValidationError
from rich.console import Console

from agentx.approval.gate import ApprovalDecision, ApprovalGate, ApprovalRequest
from agentx.budget import SpendLedger
from agentx.config import Provider, Settings
from agentx.guard.policy import GuardedExecutor, ToolPolicy
from agentx.llm.adapters import AnthropicAdapter, OpenAICompatibleAdapter
from agentx.llm.budgeted import BudgetedClient
from agentx.llm.cassette import CassetteStore
from agentx.llm.cassette_client import CassetteClient
from agentx.llm.demo import DemoClient
from agentx.loop.runner import AgentRunner, RunLimits
from agentx.runs.replay import RecordingClient, ReplayClient
from agentx.runs.store import RunStore
from agentx.tools.builtins import make_registry

DEFAULT_EVAL_OUTPUT = Path("results/scripted-eval.json")

app = typer.Typer(no_args_is_help=True, help="AgentX bounded runtime")
console = Console()


@app.command()
def doctor() -> None:
    """Report environment and non-sensitive configuration."""
    try:
        settings = Settings()
    except ValidationError as exc:
        typer.echo(f"Invalid configuration: {exc.error_count()} fields")
        raise typer.Exit(2) from exc
    typer.echo(
        json.dumps(
            {
                "python": sys.version.split()[0],
                "provider": settings.provider.value,
                "model_configured": bool(settings.model),
                "allow_live": settings.allow_live,
                "max_run_usd": str(settings.max_run_usd),
                "max_day_usd": str(settings.max_day_usd),
                "docker": shutil.which("docker") is not None,
                "ffmpeg": shutil.which("ffmpeg") is not None,
            },
            indent=2,
        )
    )


async def ask_approval(request: ApprovalRequest) -> ApprovalDecision:
    console.print(f"[yellow]APPROVAL REQUEST[/yellow] {request.tool}")
    console.print(json.dumps(request.arguments, ensure_ascii=False, indent=2))
    console.print(f"Provenance (best effort): {request.provenance}")
    return ApprovalDecision(approved=typer.confirm("Approve EXACT arguments?", default=False))


async def _run(
    task: str,
    *,
    demo: bool,
    record_synthetic: bool,
    side_effects: bool,
) -> dict[str, Any]:
    config = Settings()
    run_id = uuid.uuid4().hex
    workspace = Path(".local")
    sandbox = workspace / "sandbox"
    from sandbox.bootstrap import bootstrap

    bootstrap(sandbox)
    registry = make_registry(sandbox)
    allowed = {"calculator", "read_file", "list_dir", "search_files", "sql_query", "http_get"}
    if side_effects:
        allowed |= {"write_note", "send_email_mock"}
    guard = GuardedExecutor(
        registry,
        ToolPolicy(permitted=allowed),
        ApprovalGate(ask_approval if side_effects else None, timeout_s=30),
    )
    store = RunStore(workspace / "runs.sqlite3", allow_synthetic_replay=record_synthetic)
    async with httpx.AsyncClient(timeout=20) as http:
        if demo:
            client: Any = DemoClient()
        elif config.provider == Provider.CASSETTE:
            client = CassetteClient(CassetteStore(Path("sandbox/cassettes")))
        else:
            config.assert_provider_implemented()
            if config.provider == Provider.ANTHROPIC:
                assert config.anthropic_api_key is not None
                adapter = AnthropicAdapter(
                    http,
                    endpoint="https://api.anthropic.com/v1/messages",
                    model=config.model,
                    headers={
                        "x-api-key": config.anthropic_api_key.get_secret_value(),
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                )
            else:
                assert config.openai_api_key is not None
                adapter = OpenAICompatibleAdapter(
                    http,
                    endpoint=config.openai_base_url.rstrip("/") + "/chat/completions",
                    model=config.model,
                    headers={"authorization": f"Bearer {config.openai_api_key.get_secret_value()}"},
                )
            ledger = SpendLedger(
                Path(config.budget_db_path),
                per_run_usd=config.max_run_usd,
                per_day_usd=config.max_day_usd,
            )
            client = BudgetedClient(
                adapter,
                ledger,
                run_id=run_id,
                max_input_tokens=config.max_input_tokens,
                input_per_million_usd=config.input_usd_per_million,
                output_per_million_usd=config.output_usd_per_million,
            )
        if record_synthetic:
            if not demo:
                raise ValueError("Recording is restricted to reviewed synthetic --demo runs")
            client = RecordingClient(client, store, run_id)
        runtime = AgentRunner(
            client,
            registry,
            allowed_tools=allowed,
            guarded_executor=guard,
            limits=RunLimits(),
            store=store,
            trace_path=str(workspace / "traces" / f"{run_id}.jsonl"),
        )
        outcome = await runtime.run(task, run_id=run_id)
    return outcome.model_dump(mode="json")


@app.command("run")
def run_task(
    task: str,
    demo: bool = typer.Option(False, help="Run a scripted arithmetic demo, not a real LLM"),
    record_synthetic: bool = typer.Option(False, help="Opt in to synthetic cassette recording"),
    side_effects: bool = typer.Option(
        False, help="Enable interactive approval for mock side effects"
    ),
) -> None:
    """Run bounded agent, default offline. Use --demo for a reproducible example."""
    try:
        typer.echo(
            json.dumps(
                asyncio.run(
                    _run(
                        task,
                        demo=demo,
                        record_synthetic=record_synthetic,
                        side_effects=side_effects,
                    )
                ),
                indent=2,
            )
        )
    except (ValidationError, RuntimeError, ValueError) as exc:
        console.print(f"[red]Run unavailable:[/red] {type(exc).__name__}: {exc}")
        raise typer.Exit(code=2) from exc


@app.command()
def eval(
    repeats: int = typer.Option(3, min=1, max=20),
    output: Path = typer.Option(DEFAULT_EVAL_OUTPUT),
) -> None:
    """Run synthetic fixture tests. Not real model performance."""
    from eval.harness import evaluate

    outcome = asyncio.run(evaluate(output, repeats))
    console.print("OFFLINE SCRIPTED CHECKS ONLY. No real-model claims.")
    console.print(
        json.dumps(
            {
                "output": str(output),
                "benign": outcome["synthetic_benign_runtime_pass"],
                "mock_exfil_prevented": outcome["synthetic_mock_exfil_prevented"],
            },
            indent=2,
        )
    )


@app.command()
def trace(run_id: str) -> None:
    """Inspect redacted JSONL trace from a previous local run."""
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise typer.BadParameter("run_id must be a 32-character hex ID")
    path = Path(".local/traces") / f"{run_id}.jsonl"
    if not path.exists():
        raise typer.BadParameter("no trace for this run ID")
    for line in path.read_text(encoding="utf-8").splitlines():
        console.print_json(line)


@app.command()
def replay(run_id: str, task: str) -> None:
    """Replay exactly an opt-in synthetic run; original task is required."""
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise typer.BadParameter("run_id must be a 32-character hex ID")

    async def _replay() -> dict[str, Any]:
        sandbox = Path(".local/sandbox")
        from sandbox.bootstrap import bootstrap

        bootstrap(sandbox)
        registry = make_registry(sandbox)
        store = RunStore(Path(".local/runs.sqlite3"), allow_synthetic_replay=True)
        runtime = AgentRunner(
            ReplayClient(store, run_id),
            registry,
            allowed_tools={
                "calculator",
                "read_file",
                "list_dir",
                "search_files",
                "sql_query",
                "http_get",
            },
        )
        return (await runtime.run(task)).model_dump(mode="json")

    typer.echo(json.dumps(asyncio.run(_replay()), indent=2))


if __name__ == "__main__":
    app()

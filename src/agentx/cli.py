"""M0 configuration inspection; agent commands arrive in M7."""

import json
import platform
import shutil
import sys

import typer
from pydantic import ValidationError

from agentx.config import Settings

app = typer.Typer(no_args_is_help=True, help="AgentX development CLI (M0 scaffold).")


@app.command()
def doctor() -> None:
    """Show environment and safe configuration without printing secrets."""
    try:
        settings = Settings()
    except ValidationError as exc:
        typer.echo(f"Invalid configuration: {exc.error_count()} field(s) failed validation")
        raise typer.Exit(code=2) from exc
    summary = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "provider": settings.provider.value,
        "max_run_usd": str(settings.max_run_usd),
        "max_day_usd": str(settings.max_day_usd),
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "docker": shutil.which("docker") is not None,
        "live_calls_implemented": False,
    }
    typer.echo(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    app()

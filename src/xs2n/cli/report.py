from __future__ import annotations

from pathlib import Path
import subprocess

import typer

from xs2n.agents import (
    DEFAULT_REPORT_MODEL,
    DEFAULT_REPORT_RUNS_PATH,
    DEFAULT_TAXONOMY_PATH,
    DEFAULT_WINDOW_MINUTES,
    run_digest_report,
)
from xs2n.storage import DEFAULT_REPORT_STATE_PATH, DEFAULT_TIMELINE_PATH

report_app = typer.Typer(
    help="Report pipeline commands.",
    no_args_is_help=True,
)


@report_app.callback()
def report_main() -> None:
    """Manage report pipeline utilities."""


def _run_codex_command(command: list[str]) -> None:
    try:
        completed = subprocess.run(command, check=False)
    except FileNotFoundError as error:
        typer.echo(
            "Could not find the Codex CLI binary. Install it with "
            "`npm install -g @openai/codex` and retry.",
            err=True,
        )
        raise typer.Exit(code=1) from error
    except OSError as error:
        typer.echo(f"Could not run {' '.join(command)}: {error}", err=True)
        raise typer.Exit(code=1) from error

    if completed.returncode != 0:
        raise typer.Exit(code=completed.returncode or 1)


@report_app.command("auth")
def auth(
    status: bool = typer.Option(
        False,
        "--status",
        help="Show Codex authentication status.",
    ),
    logout: bool = typer.Option(
        False,
        "--logout",
        help="Log out from Codex authentication.",
    ),
    device_auth: bool = typer.Option(
        False,
        "--device-auth",
        help="Use Codex device-code auth flow for headless environments.",
    ),
    codex_bin: str = typer.Option(
        "codex",
        "--codex-bin",
        help="Codex CLI executable name/path.",
    ),
) -> None:
    """Authenticate report pipeline access via ChatGPT Codex auth."""

    if status and logout:
        raise typer.BadParameter("Use either --status or --logout, not both.")
    if (status or logout) and device_auth:
        raise typer.BadParameter("--device-auth can only be used for login.")

    if status:
        _run_codex_command([codex_bin, "login", "status"])
        return

    if logout:
        _run_codex_command([codex_bin, "logout"])
        return

    command = [codex_bin, "login"]
    if device_auth:
        command.append("--device-auth")
    _run_codex_command(command)


@report_app.command("digest")
def digest(
    timeline_file: Path = typer.Option(
        DEFAULT_TIMELINE_PATH,
        "--timeline-file",
        help="Timeline JSON produced by ingestion.",
    ),
    output_dir: Path = typer.Option(
        DEFAULT_REPORT_RUNS_PATH,
        "--output-dir",
        help="Directory where report run artifacts are written.",
    ),
    state_file: Path = typer.Option(
        DEFAULT_REPORT_STATE_PATH,
        "--state-file",
        help="JSON file used to remember heated threads between runs.",
    ),
    taxonomy_file: Path = typer.Option(
        DEFAULT_TAXONOMY_PATH,
        "--taxonomy-file",
        help="Editable taxonomy JSON file.",
    ),
    window_minutes: int = typer.Option(
        DEFAULT_WINDOW_MINUTES,
        "--window-minutes",
        min=1,
        help="Freshness window used on the first run or when no prior run state exists.",
    ),
    model: str = typer.Option(
        DEFAULT_REPORT_MODEL,
        "--model",
        help="OpenAI model name used for structured digest steps.",
    ),
) -> None:
    """Generate a traceable markdown digest from timeline data."""

    try:
        result = run_digest_report(
            timeline_file=timeline_file,
            output_dir=output_dir,
            state_file=state_file,
            taxonomy_file=taxonomy_file,
            window_minutes=window_minutes,
            model=model,
        )
    except RuntimeError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error

    typer.echo(
        f"Digest run {result.run_id}: selected {result.selected_count} entries, "
        f"kept {result.kept_count} units, produced {result.issue_count} issues "
        f"({result.heated_count} heated). Saved markdown to {result.digest_path}."
    )

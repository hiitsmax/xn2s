from __future__ import annotations

import subprocess

import typer

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

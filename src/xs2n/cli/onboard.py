from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from xs2n.cli.helpers import sanitize_cli_parameters
from xs2n.cli.parameters import process_paste_parameters
from xs2n.profile.auth import prompt_login
from xs2n.profile.following import run_import_following_handles
from xs2n.profile.helpers import build_entries_from_handles
from xs2n.storage import DEFAULT_SOURCES_PATH, merge_profiles


def onboard(
    paste: bool = typer.Option(
        False,
        "-p",
        "--paste",
        help="Paste handles interactively.",
    ),
    from_following: str | None = typer.Option(
        None,
        "-f",
        "--from-following",
        help="Import profiles from who this account follows.",
    ),
    wizard: bool = typer.Option(
        False,
        "--wizard",
        help="Run an interactive onboarding wizard.",
    ),
    cookies_file: Path = typer.Option(
        Path("cookies.json"),
        "--cookies-file",
        help="Twikit cookies file for authenticated scraping.",
    ),
    limit: int = typer.Option(
        200,
        "--limit",
        min=1,
        max=1000,
        help="Maximum number of profiles to import from following list.",
    ),
    sources_file: Path = typer.Option(
        DEFAULT_SOURCES_PATH,
        "--sources-file",
        help="Where profile sources are stored.",
    ),
) -> None:
    """Onboard source profiles by pasting handles or importing followings."""

    parameters: dict[str, Any] = {
        "paste": paste,
        "from_following": from_following,
        "wizard": wizard,
        "cookies_file": cookies_file,
        "limit": limit,
        "sources_file": sources_file,
    }

    sanitize_cli_parameters(parameters)

    invalid: list[str] = []
    if parameters["paste"]:
        _, invalid = process_paste_parameters(parameters)

    if parameters["from_following"]:
        account = str(parameters["from_following"])
        handles = run_import_following_handles(
            account_screen_name=account,
            cookies_file=Path(parameters["cookies_file"]),
            limit=int(parameters["limit"]),
            prompt_login=prompt_login,
        )
        if not handles:
            typer.echo("No handles imported from following list.")
            raise typer.Exit(code=1)

        result = merge_profiles(
            build_entries_from_handles(handles, source="following_import"),
            path=Path(parameters["sources_file"]),
        )
        typer.echo(
            f"Imported {len(handles)} followings. "
            f"Added {result.added}, skipped {result.skipped_duplicates} duplicates."
        )

    if invalid:
        typer.echo(f"Skipped invalid tokens: {', '.join(invalid)}")

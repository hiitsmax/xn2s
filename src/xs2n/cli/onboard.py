from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from twikit.errors import Forbidden, UserNotFound

from xs2n.cli.helpers import (
    maybe_bootstrap_cookies_from_local_browser,
    normalize_following_account,
    retry_after_cloudflare_block,
    sanitize_cli_parameters,
)
from xs2n.cli.parameters import process_paste_parameters
from xs2n.profile.auth import prompt_login
from xs2n.profile.following import (
    AUTHENTICATED_ACCOUNT_SENTINEL,
    DEFAULT_IMPORT_FOLLOWING_HANDLES,
    IMPORT_FOLLOWING_HANDLES_LIMIT,
    run_import_following_handles,
)
from xs2n.profile.helpers import build_entries_from_handles
from xs2n.storage import DEFAULT_SOURCES_PATH, merge_profiles, replace_profiles


def import_following_with_recovery(
    account: str,
    cookies_file: Path,
    limit: int,
) -> list[str]:
    account_screen_name = account

    def retry_import() -> list[str]:
        return run_import_following_handles(
            account_screen_name=account_screen_name,
            cookies_file=cookies_file,
            limit=limit,
            prompt_login=prompt_login,
        )

    maybe_bootstrap_cookies_from_local_browser(cookies_file)

    try:
        return retry_import()
    except UserNotFound:
        typer.echo(
            f"X profile '{account_screen_name}' was not found.",
            err=True,
        )
        account_screen_name = normalize_following_account(
            typer.prompt("X screen name (@, plain, or x.com URL)")
        )
        typer.echo(f"Retrying with @{account_screen_name}...")
        return retry_import()
    except Forbidden as error:
        return retry_after_cloudflare_block(
            retry_operation=retry_import,
            cookies_file=cookies_file,
            cloudflare_error=error,
        )


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
    refresh_following: bool = typer.Option(
        False,
        "--refresh-following",
        help=(
            "Replace the source catalog with the authenticated account's current "
            "following list."
        ),
    ),
    cookies_file: Path = typer.Option(
        Path("cookies.json"),
        "--cookies-file",
        help="Twikit cookies file for authenticated scraping.",
    ),
    limit: int = typer.Option(
        DEFAULT_IMPORT_FOLLOWING_HANDLES,
        "--limit",
        min=1,
        max=IMPORT_FOLLOWING_HANDLES_LIMIT,
        help="Maximum number of profiles to import from following list.",
    ),
    sources_file: Path = typer.Option(
        DEFAULT_SOURCES_PATH,
        "--sources-file",
        help="Where profile sources are stored.",
    ),
) -> None:
    """Onboard source profiles by pasting handles or importing followings."""

    if wizard:
        raise typer.BadParameter(
            "--wizard is no longer a separate onboarding mode. "
            "Run `xs2n onboard` for the interactive prompt, or choose "
            "--paste, --from-following, or --refresh-following explicitly."
        )

    parameters: dict[str, Any] = {
        "paste": paste,
        "from_following": from_following,
        "refresh_following": refresh_following,
        "cookies_file": cookies_file,
        "limit": limit,
        "sources_file": sources_file,
    }

    sanitize_cli_parameters(parameters)

    invalid: list[str] = []
    if parameters["paste"]:
        _, invalid = process_paste_parameters(
            sources_file=Path(parameters["sources_file"])
        )

    if parameters["refresh_following"]:
        handles = import_following_with_recovery(
            account=AUTHENTICATED_ACCOUNT_SENTINEL,
            cookies_file=Path(parameters["cookies_file"]),
            limit=int(parameters["limit"]),
        )
        result = replace_profiles(
            build_entries_from_handles(handles, source="following_refresh"),
            path=Path(parameters["sources_file"]),
        )
        typer.echo(
            "Refreshed source catalog from the authenticated account's following list."
        )
        typer.echo(f"Stored {result.added} profiles in the sources catalog.")

    elif parameters["from_following"]:
        account = str(parameters["from_following"])
        handles = import_following_with_recovery(
            account=account,
            cookies_file=Path(parameters["cookies_file"]),
            limit=int(parameters["limit"]),
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

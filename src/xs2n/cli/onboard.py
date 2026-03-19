from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from twikit.errors import Forbidden, UserNotFound

from xs2n.cli.helpers import normalize_following_account, sanitize_cli_parameters
from xs2n.cli.parameters import process_paste_parameters
from xs2n.profile.auth import (
    is_cloudflare_block_error,
    prompt_login,
)
from xs2n.profile.browser_cookies import (
    BrowserCookieCandidate,
    describe_cookie_candidate,
    discover_x_cookie_candidates,
    maybe_warn_keychain_prompt,
    write_cookie_candidate,
)
from xs2n.profile.following import (
    AUTHENTICATED_ACCOUNT_SENTINEL,
    DEFAULT_IMPORT_FOLLOWING_HANDLES,
    IMPORT_FOLLOWING_HANDLES_LIMIT,
    run_import_following_handles,
)
from xs2n.profile.helpers import build_entries_from_handles
from xs2n.profile.playwright import bootstrap_cookies_via_browser
from xs2n.storage import DEFAULT_SOURCES_PATH, merge_profiles, replace_profiles


def choose_cookie_candidate(candidates: list[BrowserCookieCandidate]) -> BrowserCookieCandidate:
    if len(candidates) == 1:
        candidate = candidates[0]
        typer.echo(
            "Found logged-in browser session: "
            f"{describe_cookie_candidate(candidate)}. Using it."
        )
        return candidate

    typer.echo("Found multiple logged-in browser sessions:")
    for index, candidate in enumerate(candidates, start=1):
        typer.echo(f"{index}. {describe_cookie_candidate(candidate)}")

    while True:
        raw_choice = typer.prompt("Select session number", default="1")
        try:
            choice = int(raw_choice)
        except ValueError:
            typer.echo("Please enter a valid number.", err=True)
            continue

        if 1 <= choice <= len(candidates):
            return candidates[choice - 1]

        typer.echo("Choice out of range. Try again.", err=True)


def bootstrap_cookies_from_local_browser_with_choice(cookies_file: Path) -> Path:
    maybe_warn_keychain_prompt(echo=typer.echo)
    candidates = discover_x_cookie_candidates(resolve_profiles=True)
    selected = choose_cookie_candidate(candidates)
    return write_cookie_candidate(selected, cookies_file)


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

    if not cookies_file.exists():
        typer.echo("Checking local browser cookies for logged-in X sessions...")
        try:
            saved_path = bootstrap_cookies_from_local_browser_with_choice(cookies_file)
            typer.echo(f"Saved browser cookies to {saved_path}.")
        except RuntimeError as local_cookie_error:
            typer.echo(
                "No usable local browser cookies were found. "
                f"Details: {local_cookie_error}",
                err=True,
            )

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
        if not is_cloudflare_block_error(error):
            raise

        typer.echo(
            "X blocked this automated login request (Cloudflare 403).",
            err=True,
        )
        typer.echo(
            "Trying to refresh cookies from your local browser first.",
            err=True,
        )
        try:
            saved_path = bootstrap_cookies_from_local_browser_with_choice(cookies_file)
            typer.echo(f"Imported local browser cookies to {saved_path}. Retrying...")
            return retry_import()
        except RuntimeError as local_cookie_error:
            typer.echo(
                f"Could not import cookies from local browser: {local_cookie_error}",
                err=True,
            )
        except Forbidden as local_retry_error:
            if not is_cloudflare_block_error(local_retry_error):
                raise
            typer.echo(
                "Still blocked by Cloudflare after importing local browser cookies.",
                err=True,
            )

        typer.echo(
            "We can open a real browser to refresh session cookies, then retry automatically.",
            err=True,
        )
        recover_now = typer.confirm("Open browser login and retry now?", default=True)
        if not recover_now:
            raise typer.Exit(code=1)

        try:
            saved_path = bootstrap_cookies_via_browser(cookies_file)
            typer.echo(f"Saved browser cookies to {saved_path}. Retrying...")
            return retry_import()
        except RuntimeError as bootstrap_error:
            typer.echo(f"Could not bootstrap cookies: {bootstrap_error}", err=True)
            raise typer.Exit(code=1) from bootstrap_error
        except Forbidden as retry_error:
            if is_cloudflare_block_error(retry_error):
                typer.echo(
                    "Still blocked by Cloudflare after browser login. "
                    "Try again from a normal residential/mobile network.",
                    err=True,
                )
                raise typer.Exit(code=1) from retry_error
            raise


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

    parameters: dict[str, Any] = {
        "paste": paste,
        "from_following": from_following,
        "wizard": wizard,
        "refresh_following": refresh_following,
        "cookies_file": cookies_file,
        "limit": limit,
        "sources_file": sources_file,
    }

    sanitize_cli_parameters(parameters)

    invalid: list[str] = []
    if parameters["paste"]:
        _, invalid = process_paste_parameters(parameters)

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

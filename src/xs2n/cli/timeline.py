from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import typer
from twikit.errors import Forbidden, UserNotFound

from xs2n.cli.helpers import normalize_following_account
from xs2n.cli.onboard import bootstrap_cookies_from_local_browser_with_choice
from xs2n.profile.auth import is_cloudflare_block_error, prompt_login
from xs2n.profile.playwright import bootstrap_cookies_via_browser
from xs2n.profile.timeline import (
    DEFAULT_IMPORT_TIMELINE,
    IMPORT_TIMELINE_LIMIT,
    TimelineFetchResult,
    run_import_timeline_entries,
)
from xs2n.timeline_storage import DEFAULT_TIMELINE_PATH, merge_timeline_entries


def parse_since_datetime(value: str) -> datetime:
    candidate = value.strip()
    if not candidate:
        raise typer.BadParameter("Provide --since as an ISO datetime.")

    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as error:
        raise typer.BadParameter(
            "Invalid --since value. Use ISO datetime format, for example: "
            "2026-03-01T00:00:00Z"
        ) from error

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def import_timeline_with_recovery(
    account: str,
    cookies_file: Path,
    since_datetime: datetime,
    limit: int,
) -> TimelineFetchResult:
    account_screen_name = account

    def retry_import() -> TimelineFetchResult:
        return run_import_timeline_entries(
            account_screen_name=account_screen_name,
            cookies_file=cookies_file,
            since_datetime=since_datetime,
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


def timeline(
    account: str = typer.Option(
        ...,
        "-a",
        "--account",
        help="X account handle (or x.com URL) to scrape.",
    ),
    since: str = typer.Option(
        ...,
        "--since",
        help="Include posts and retweets since this ISO datetime (UTC if timezone omitted).",
    ),
    cookies_file: Path = typer.Option(
        Path("cookies.json"),
        "--cookies-file",
        help="Twikit cookies file for authenticated scraping.",
    ),
    limit: int = typer.Option(
        DEFAULT_IMPORT_TIMELINE,
        "--limit",
        min=1,
        max=IMPORT_TIMELINE_LIMIT,
        help="Maximum number of timeline entries to ingest in this run.",
    ),
    timeline_file: Path = typer.Option(
        DEFAULT_TIMELINE_PATH,
        "--timeline-file",
        help="Where timeline entries are stored.",
    ),
) -> None:
    """Ingest posts and retweets from an account since a datetime."""

    normalized_account = normalize_following_account(account)
    since_datetime = parse_since_datetime(since)

    fetch_result = import_timeline_with_recovery(
        account=normalized_account,
        cookies_file=cookies_file,
        since_datetime=since_datetime,
        limit=limit,
    )

    if not fetch_result.entries:
        typer.echo(
            "No posts/retweets found at or after "
            f"{since_datetime.isoformat()} for @{normalized_account}."
        )
        return

    merge_result = merge_timeline_entries(fetch_result.entries, path=timeline_file)
    typer.echo(
        f"Scanned {fetch_result.scanned} timeline items for @{normalized_account}. "
        f"Matched {len(fetch_result.entries)} items since {since_datetime.isoformat()} "
        f"(skipped {fetch_result.skipped_old} older items). "
        f"Added {merge_result.added}, skipped {merge_result.skipped_duplicates} duplicates. "
        f"Saved to {timeline_file}."
    )

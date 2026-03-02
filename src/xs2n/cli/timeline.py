from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any

import typer
from twikit.errors import Forbidden, TooManyRequests, UserNotFound

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
from xs2n.storage import DEFAULT_SOURCES_PATH, migrate_legacy_sources_yaml, load_sources
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
    page_delay_seconds: float = 0.0,
) -> TimelineFetchResult:
    account_screen_name = account

    def retry_import() -> TimelineFetchResult:
        return run_import_timeline_entries(
            account_screen_name=account_screen_name,
            cookies_file=cookies_file,
            since_datetime=since_datetime,
            limit=limit,
            prompt_login=prompt_login,
            page_delay_seconds=page_delay_seconds,
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


def _legacy_sources_path_for(path: Path) -> Path:
    return path.with_suffix(".yaml")


def _load_handles_from_sources(path: Path) -> list[str]:
    doc = load_sources(path)
    profiles = doc.get("profiles")
    if not isinstance(profiles, list):
        return []

    handles: list[str] = []
    seen: set[str] = set()
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        raw_handle = profile.get("handle")
        if not isinstance(raw_handle, str):
            continue
        try:
            normalized = normalize_following_account(raw_handle)
        except typer.BadParameter:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        handles.append(normalized)
    return handles


def _single_account_summary(
    account: str,
    since_datetime: datetime,
    fetch_result: TimelineFetchResult,
    merge_result_added: int,
    merge_result_duplicates: int,
    timeline_file: Path,
) -> None:
    typer.echo(
        f"Scanned {fetch_result.scanned} timeline items for @{account}. "
        f"Matched {len(fetch_result.entries)} items since {since_datetime.isoformat()} "
        f"(skipped {fetch_result.skipped_old} older items). "
        f"Added {merge_result_added}, skipped {merge_result_duplicates} duplicates. "
        f"Saved to {timeline_file}."
    )


def _rate_limit_wait_seconds(
    error: TooManyRequests,
    fallback_wait_seconds: int,
    max_wait_seconds: int,
) -> int:
    reset_epoch = getattr(error, "rate_limit_reset", None)
    if isinstance(reset_epoch, int):
        now_epoch = int(datetime.now(timezone.utc).timestamp())
        computed_wait = max(1, reset_epoch - now_epoch + 1)
    else:
        computed_wait = fallback_wait_seconds
    return max(1, min(computed_wait, max_wait_seconds))


def _active_wait_for_rate_limit(
    *,
    account: str,
    wait_seconds: int,
    poll_seconds: int,
    retry_index: int,
    max_retries: int,
) -> None:
    remaining = wait_seconds
    while remaining > 0:
        typer.echo(
            "Hit X rate limit (429) for "
            f"@{account}. Retry {retry_index}/{max_retries} in {remaining}s...",
            err=True,
        )
        sleep_for = min(poll_seconds, remaining)
        time.sleep(sleep_for)
        remaining -= sleep_for


def _fetch_with_rate_limit_retries(
    *,
    account: str,
    cookies_file: Path,
    since_datetime: datetime,
    limit: int,
    page_delay_seconds: float,
    wait_on_rate_limit: bool,
    rate_limit_wait_seconds: int,
    rate_limit_poll_seconds: int,
    max_rate_limit_wait_seconds: int,
    max_rate_limit_retries: int,
) -> TimelineFetchResult:
    retries = 0

    while True:
        try:
            return import_timeline_with_recovery(
                account=account,
                cookies_file=cookies_file,
                since_datetime=since_datetime,
                limit=limit,
                page_delay_seconds=page_delay_seconds,
            )
        except TooManyRequests as error:
            if not wait_on_rate_limit:
                raise

            retries += 1
            if retries > max_rate_limit_retries:
                typer.echo(
                    "Rate limit persisted for "
                    f"@{account} after {max_rate_limit_retries} retries.",
                    err=True,
                )
                raise

            wait_seconds = _rate_limit_wait_seconds(
                error=error,
                fallback_wait_seconds=rate_limit_wait_seconds,
                max_wait_seconds=max_rate_limit_wait_seconds,
            )
            _active_wait_for_rate_limit(
                account=account,
                wait_seconds=wait_seconds,
                poll_seconds=rate_limit_poll_seconds,
                retry_index=retries,
                max_retries=max_rate_limit_retries,
            )


def timeline(
    account: str | None = typer.Option(
        None,
        "-a",
        "--account",
        help="X account handle (or x.com URL) to scrape. Required unless --from-sources is used.",
    ),
    from_sources: bool = typer.Option(
        False,
        "--from-sources",
        help="Ingest timelines for every handle in sources file.",
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
    sources_file: Path = typer.Option(
        DEFAULT_SOURCES_PATH,
        "--sources-file",
        help="Where source handles are stored (used with --from-sources).",
    ),
    slow_fetch_seconds: float = typer.Option(
        1.0,
        "--slow-fetch-seconds",
        min=0.0,
        help="Delay in seconds between accounts when using --from-sources.",
    ),
    page_delay_seconds: float = typer.Option(
        0.4,
        "--page-delay-seconds",
        min=0.0,
        help="Delay in seconds between timeline pagination requests.",
    ),
    wait_on_rate_limit: bool = typer.Option(
        True,
        "--wait-on-rate-limit/--no-wait-on-rate-limit",
        help="Automatically wait and retry when X returns rate limit (429).",
    ),
    rate_limit_wait_seconds: int = typer.Option(
        900,
        "--rate-limit-wait-seconds",
        min=1,
        help="Fallback wait in seconds for 429 when reset time is unavailable.",
    ),
    rate_limit_poll_seconds: int = typer.Option(
        30,
        "--rate-limit-poll-seconds",
        min=1,
        help="How often to print wait progress during a 429 sleep window.",
    ),
    max_rate_limit_wait_seconds: int = typer.Option(
        1800,
        "--max-rate-limit-wait-seconds",
        min=1,
        help="Maximum wait duration in seconds per 429 event.",
    ),
    max_rate_limit_retries: int = typer.Option(
        30,
        "--max-rate-limit-retries",
        min=1,
        help="Maximum 429 retries per account before the run stops.",
    ),
) -> None:
    """Ingest posts and retweets since a datetime."""

    if from_sources and account:
        raise typer.BadParameter("Use either --account or --from-sources, not both.")
    if not from_sources and not account:
        raise typer.BadParameter("Provide --account or use --from-sources.")

    since_datetime = parse_since_datetime(since)

    if from_sources:
        if not sources_file.exists():
            legacy_sources_file = _legacy_sources_path_for(sources_file)
            migrated = migrate_legacy_sources_yaml(
                yaml_path=legacy_sources_file,
                json_path=sources_file,
            )
            if migrated:
                typer.echo(
                    f"Migrated {migrated} source profiles from "
                    f"{legacy_sources_file} to {sources_file}."
                )

        handles = _load_handles_from_sources(sources_file)
        if not handles:
            typer.echo(
                f"No source handles found in {sources_file}. "
                "Run `xs2n onboard` first or pass a populated sources file.",
                err=True,
            )
            raise typer.Exit(code=1)

        totals: dict[str, Any] = {
            "scanned": 0,
            "matched": 0,
            "skipped_old": 0,
            "added": 0,
            "duplicates": 0,
        }
        processed_accounts = 0
        stopped_due_to_rate_limit = False

        for index, handle in enumerate(handles, start=1):
            try:
                fetch_result = _fetch_with_rate_limit_retries(
                    account=handle,
                    cookies_file=cookies_file,
                    since_datetime=since_datetime,
                    limit=limit,
                    page_delay_seconds=page_delay_seconds,
                    wait_on_rate_limit=wait_on_rate_limit,
                    rate_limit_wait_seconds=rate_limit_wait_seconds,
                    rate_limit_poll_seconds=rate_limit_poll_seconds,
                    max_rate_limit_wait_seconds=max_rate_limit_wait_seconds,
                    max_rate_limit_retries=max_rate_limit_retries,
                )
            except TooManyRequests:
                typer.echo(
                    "Hit X rate limit (429) while ingesting "
                    f"@{handle}. Stopping batch run.",
                    err=True,
                )
                stopped_due_to_rate_limit = True
                break

            processed_accounts += 1
            totals["scanned"] += fetch_result.scanned
            totals["matched"] += len(fetch_result.entries)
            totals["skipped_old"] += fetch_result.skipped_old

            if not fetch_result.entries:
                typer.echo(
                    "No posts/retweets found at or after "
                    f"{since_datetime.isoformat()} for @{handle}."
                )
            else:
                merge_result = merge_timeline_entries(fetch_result.entries, path=timeline_file)
                totals["added"] += merge_result.added
                totals["duplicates"] += merge_result.skipped_duplicates
                _single_account_summary(
                    account=handle,
                    since_datetime=since_datetime,
                    fetch_result=fetch_result,
                    merge_result_added=merge_result.added,
                    merge_result_duplicates=merge_result.skipped_duplicates,
                    timeline_file=timeline_file,
                )

            if slow_fetch_seconds > 0 and index < len(handles):
                typer.echo(
                    f"Throttling for {slow_fetch_seconds:.2f}s before next account..."
                )
                time.sleep(slow_fetch_seconds)

        typer.echo(
            f"Processed {processed_accounts} of {len(handles)} accounts from {sources_file}. "
            f"Scanned {totals['scanned']} timeline items. "
            f"Matched {totals['matched']} items since {since_datetime.isoformat()} "
            f"(skipped {totals['skipped_old']} older items). "
            f"Added {totals['added']}, skipped {totals['duplicates']} duplicates. "
            f"Saved to {timeline_file}."
        )
        if stopped_due_to_rate_limit:
            raise typer.Exit(code=1)
        return

    normalized_account = normalize_following_account(str(account))
    try:
        fetch_result = _fetch_with_rate_limit_retries(
            account=normalized_account,
            cookies_file=cookies_file,
            since_datetime=since_datetime,
            limit=limit,
            page_delay_seconds=page_delay_seconds,
            wait_on_rate_limit=wait_on_rate_limit,
            rate_limit_wait_seconds=rate_limit_wait_seconds,
            rate_limit_poll_seconds=rate_limit_poll_seconds,
            max_rate_limit_wait_seconds=max_rate_limit_wait_seconds,
            max_rate_limit_retries=max_rate_limit_retries,
        )
    except TooManyRequests as error:
        typer.echo(
            "Hit X rate limit (429) while fetching "
            f"@{normalized_account}. Stopping run.",
            err=True,
        )
        raise typer.Exit(code=1) from error

    if not fetch_result.entries:
        typer.echo(
            "No posts/retweets found at or after "
            f"{since_datetime.isoformat()} for @{normalized_account}."
        )
        return

    merge_result = merge_timeline_entries(fetch_result.entries, path=timeline_file)
    _single_account_summary(
        account=normalized_account,
        since_datetime=since_datetime,
        fetch_result=fetch_result,
        merge_result_added=merge_result.added,
        merge_result_duplicates=merge_result.skipped_duplicates,
        timeline_file=timeline_file,
    )

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
    DEFAULT_THREAD_OTHER_REPLIES_LIMIT,
    DEFAULT_THREAD_PARENT_LIMIT,
    DEFAULT_THREAD_REPLIES_LIMIT,
    IMPORT_TIMELINE_LIMIT,
    TimelineFetchResult,
    run_import_home_latest_timeline_entries,
    run_import_timeline_entries,
)
from xs2n.storage import (
    DEFAULT_SOURCES_PATH,
    DEFAULT_TIMELINE_PATH,
    load_sources,
    merge_timeline_entries,
    migrate_legacy_sources_yaml,
)

DEFAULT_SLOW_FETCH_SECONDS = 1.0
DEFAULT_PAGE_DELAY_SECONDS = 0.4
DEFAULT_RATE_LIMIT_WAIT_SECONDS = 900
DEFAULT_RATE_LIMIT_POLL_SECONDS = 30
DEFAULT_MAX_RATE_LIMIT_WAIT_SECONDS = 1800
DEFAULT_MAX_RATE_LIMIT_RETRIES = 30


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
    thread_parent_limit: int = DEFAULT_THREAD_PARENT_LIMIT,
    thread_replies_limit: int = DEFAULT_THREAD_REPLIES_LIMIT,
    thread_other_replies_limit: int = DEFAULT_THREAD_OTHER_REPLIES_LIMIT,
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
            thread_parent_limit=thread_parent_limit,
            thread_replies_limit=thread_replies_limit,
            thread_other_replies_limit=thread_other_replies_limit,
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


def import_home_latest_with_recovery(
    cookies_file: Path,
    since_datetime: datetime,
    limit: int,
    page_delay_seconds: float = 0.0,
) -> TimelineFetchResult:
    def retry_import() -> TimelineFetchResult:
        return run_import_home_latest_timeline_entries(
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


def _home_latest_summary(
    since_datetime: datetime,
    fetch_result: TimelineFetchResult,
    merge_result_added: int,
    merge_result_duplicates: int,
    timeline_file: Path,
) -> None:
    typer.echo(
        f"Scanned {fetch_result.scanned} Home->Following timeline items. "
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
    thread_parent_limit: int,
    thread_replies_limit: int,
    thread_other_replies_limit: int,
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
                thread_parent_limit=thread_parent_limit,
                thread_replies_limit=thread_replies_limit,
                thread_other_replies_limit=thread_other_replies_limit,
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


def _fetch_home_latest_with_rate_limit_retries(
    *,
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
            return import_home_latest_with_recovery(
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
                    "Rate limit persisted for Home->Following timeline "
                    f"after {max_rate_limit_retries} retries.",
                    err=True,
                )
                raise

            wait_seconds = _rate_limit_wait_seconds(
                error=error,
                fallback_wait_seconds=rate_limit_wait_seconds,
                max_wait_seconds=max_rate_limit_wait_seconds,
            )
            _active_wait_for_rate_limit(
                account="home_latest",
                wait_seconds=wait_seconds,
                poll_seconds=rate_limit_poll_seconds,
                retry_index=retries,
                max_retries=max_rate_limit_retries,
            )


def run_timeline_ingestion(
    *,
    account: str | None,
    from_sources: bool,
    home_latest: bool,
    since: str,
    cookies_file: Path = Path("cookies.json"),
    limit: int = DEFAULT_IMPORT_TIMELINE,
    timeline_file: Path = DEFAULT_TIMELINE_PATH,
    sources_file: Path = DEFAULT_SOURCES_PATH,
    slow_fetch_seconds: float = DEFAULT_SLOW_FETCH_SECONDS,
    page_delay_seconds: float = DEFAULT_PAGE_DELAY_SECONDS,
    thread_parent_limit: int = DEFAULT_THREAD_PARENT_LIMIT,
    thread_replies_limit: int = DEFAULT_THREAD_REPLIES_LIMIT,
    thread_other_replies_limit: int = DEFAULT_THREAD_OTHER_REPLIES_LIMIT,
    wait_on_rate_limit: bool = True,
    rate_limit_wait_seconds: int = DEFAULT_RATE_LIMIT_WAIT_SECONDS,
    rate_limit_poll_seconds: int = DEFAULT_RATE_LIMIT_POLL_SECONDS,
    max_rate_limit_wait_seconds: int = DEFAULT_MAX_RATE_LIMIT_WAIT_SECONDS,
    max_rate_limit_retries: int = DEFAULT_MAX_RATE_LIMIT_RETRIES,
) -> None:
    """Run timeline ingestion with concrete Python defaults."""

    active_modes = sum((bool(account), from_sources, home_latest))
    if active_modes > 1:
        raise typer.BadParameter(
            "Use exactly one mode: --account, --from-sources, or --home-latest."
        )
    if active_modes == 0:
        raise typer.BadParameter(
            "Provide exactly one mode: --account, --from-sources, or --home-latest."
        )

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
                    thread_parent_limit=thread_parent_limit,
                    thread_replies_limit=thread_replies_limit,
                    thread_other_replies_limit=thread_other_replies_limit,
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
                    "No posts/replies/retweets found at or after "
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

    if home_latest:
        try:
            fetch_result = _fetch_home_latest_with_rate_limit_retries(
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
                "Hit X rate limit (429) while fetching Home->Following latest timeline. "
                "Stopping run.",
                err=True,
            )
            raise typer.Exit(code=1) from error

        if not fetch_result.entries:
            typer.echo(
                "No Home->Following timeline items found at or after "
                f"{since_datetime.isoformat()}."
            )
            return

        merge_result = merge_timeline_entries(fetch_result.entries, path=timeline_file)
        _home_latest_summary(
            since_datetime=since_datetime,
            fetch_result=fetch_result,
            merge_result_added=merge_result.added,
            merge_result_duplicates=merge_result.skipped_duplicates,
            timeline_file=timeline_file,
        )
        return

    normalized_account = normalize_following_account(str(account))
    try:
        fetch_result = _fetch_with_rate_limit_retries(
            account=normalized_account,
            cookies_file=cookies_file,
            since_datetime=since_datetime,
            limit=limit,
            page_delay_seconds=page_delay_seconds,
            thread_parent_limit=thread_parent_limit,
            thread_replies_limit=thread_replies_limit,
            thread_other_replies_limit=thread_other_replies_limit,
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
            "No posts/replies/retweets found at or after "
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


def timeline(
    account: str | None = typer.Option(
        None,
        "-a",
        "--account",
        help=(
            "X account handle (or x.com URL) to scrape. "
            "Required unless --from-sources or --home-latest is used."
        ),
    ),
    from_sources: bool = typer.Option(
        False,
        "--from-sources",
        help="Ingest timelines for every handle in sources file.",
    ),
    home_latest: bool = typer.Option(
        False,
        "--home-latest",
        help="Ingest authenticated Home -> Following latest timeline.",
    ),
    since: str = typer.Option(
        ...,
        "--since",
        help="Include posts, replies, and retweets since this ISO datetime (UTC if timezone omitted).",
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
        DEFAULT_SLOW_FETCH_SECONDS,
        "--slow-fetch-seconds",
        min=0.0,
        help="Delay in seconds between accounts when using --from-sources.",
    ),
    page_delay_seconds: float = typer.Option(
        DEFAULT_PAGE_DELAY_SECONDS,
        "--page-delay-seconds",
        min=0.0,
        help="Delay in seconds between timeline pagination requests.",
    ),
    thread_parent_limit: int = typer.Option(
        DEFAULT_THREAD_PARENT_LIMIT,
        "--thread-parent-limit",
        min=0,
        help="Max parent-chain context tweets hydrated for reply threads (0 disables).",
    ),
    thread_replies_limit: int = typer.Option(
        DEFAULT_THREAD_REPLIES_LIMIT,
        "--thread-replies-limit",
        min=0,
        help="Max recursive thread replies to add across conversations (0 disables).",
    ),
    thread_other_replies_limit: int = typer.Option(
        DEFAULT_THREAD_OTHER_REPLIES_LIMIT,
        "--thread-other-replies-limit",
        min=0,
        help="Max replies authored by non-target accounts to include (0 excludes them).",
    ),
    wait_on_rate_limit: bool = typer.Option(
        True,
        "--wait-on-rate-limit/--no-wait-on-rate-limit",
        help="Automatically wait and retry when X returns rate limit (429).",
    ),
    rate_limit_wait_seconds: int = typer.Option(
        DEFAULT_RATE_LIMIT_WAIT_SECONDS,
        "--rate-limit-wait-seconds",
        min=1,
        help="Fallback wait in seconds for 429 when reset time is unavailable.",
    ),
    rate_limit_poll_seconds: int = typer.Option(
        DEFAULT_RATE_LIMIT_POLL_SECONDS,
        "--rate-limit-poll-seconds",
        min=1,
        help="How often to print wait progress during a 429 sleep window.",
    ),
    max_rate_limit_wait_seconds: int = typer.Option(
        DEFAULT_MAX_RATE_LIMIT_WAIT_SECONDS,
        "--max-rate-limit-wait-seconds",
        min=1,
        help="Maximum wait duration in seconds per 429 event.",
    ),
    max_rate_limit_retries: int = typer.Option(
        DEFAULT_MAX_RATE_LIMIT_RETRIES,
        "--max-rate-limit-retries",
        min=1,
        help="Maximum 429 retries per account before the run stops.",
    ),
) -> None:
    """Ingest posts, replies, and retweets since a datetime."""
    run_timeline_ingestion(
        account=account,
        from_sources=from_sources,
        home_latest=home_latest,
        since=since,
        cookies_file=cookies_file,
        limit=limit,
        timeline_file=timeline_file,
        sources_file=sources_file,
        slow_fetch_seconds=slow_fetch_seconds,
        page_delay_seconds=page_delay_seconds,
        thread_parent_limit=thread_parent_limit,
        thread_replies_limit=thread_replies_limit,
        thread_other_replies_limit=thread_other_replies_limit,
        wait_on_rate_limit=wait_on_rate_limit,
        rate_limit_wait_seconds=rate_limit_wait_seconds,
        rate_limit_poll_seconds=rate_limit_poll_seconds,
        max_rate_limit_wait_seconds=max_rate_limit_wait_seconds,
        max_rate_limit_retries=max_rate_limit_retries,
    )

from __future__ import annotations

import asyncio
from hashlib import sha256
from pathlib import Path
import time

from twscrape import API
from twscrape.account import Account
from twscrape.login import get_guest_token

from xs2n.agents.schemas import Post, Thread
from xs2n.twitter_cookies import resolve_twitter_cookies


TWSCRAPE_STATE_DIR_ENV_VAR = "XS2N_TWSCRAPE_STATE_DIR"
DEFAULT_RATE_LIMIT_WAIT_SECONDS = 60
MAX_RATE_LIMIT_RETRIES = 5
DEFAULT_HANDLE_BATCH_SIZE = 10
DEFAULT_HANDLE_TIMEOUT_SECONDS = 45.0
DEFAULT_MAX_HANDLE_RETRIES = 2


def get_twscrape_state_dir() -> Path:
    import os

    override = os.environ.get(TWSCRAPE_STATE_DIR_ENV_VAR, "").strip()
    if override:
        return Path(override)
    return Path.home() / "Library" / "Application Support" / "xs2n" / "twscrape"


def _get_twscrape_db_file() -> Path:
    return get_twscrape_state_dir() / "accounts.db"


def _build_cookie_account_name(cookies: str) -> str:
    digest = sha256(cookies.encode("utf-8")).hexdigest()[:12]
    return f"xs2n-cookie-{digest}"


def cookie_map_from_httpx_cookies(cookies) -> dict[str, str]:  # noqa: ANN001
    if isinstance(cookies, dict):
        return {key: value for key, value in cookies.items() if value}

    cookie_map: dict[str, str] = {}
    for cookie in cookies.jar:
        if cookie.name and cookie.value:
            cookie_map[cookie.name] = cookie.value
    return cookie_map


def get_rate_limit_wait_seconds(response, current_time=time.time) -> int:  # noqa: ANN001, B008
    reset_header = response.headers.get("x-rate-limit-reset")
    if reset_header:
        try:
            wait_seconds = int(float(reset_header) - current_time()) + 1
        except ValueError:
            wait_seconds = DEFAULT_RATE_LIMIT_WAIT_SECONDS
        return max(1, wait_seconds)

    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return max(1, int(float(retry_after)))
        except ValueError:
            return DEFAULT_RATE_LIMIT_WAIT_SECONDS

    return DEFAULT_RATE_LIMIT_WAIT_SECONDS


async def get_with_rate_limit_retry(
    client,
    url: str,
    *,
    params,
    sleep=asyncio.sleep,
    current_time=time.time,  # noqa: B008
    max_retries: int = MAX_RATE_LIMIT_RETRIES,
):  # noqa: ANN001
    attempts = 0
    while True:
        response = await client.get(url, params=params)
        if response.status_code != 429:
            response.raise_for_status()
            return response

        if attempts >= max_retries:
            response.raise_for_status()

        wait_seconds = get_rate_limit_wait_seconds(response, current_time=current_time)
        await sleep(wait_seconds)
        attempts += 1


def _build_post_from_tweet(tweet) -> Post:  # noqa: ANN001
    user = getattr(tweet, "user", None)
    author_handle = getattr(user, "username", "") if user is not None else ""
    return Post(
        post_id=str(getattr(tweet, "id")),
        author_handle=author_handle,
        created_at=getattr(tweet, "date"),
        text=getattr(tweet, "rawContent", ""),
        url=getattr(tweet, "url", ""),
    )


def build_threads_from_tweets(account_handle: str, tweets) -> list[Thread]:  # noqa: ANN001
    grouped_posts: dict[str, list[Post]] = {}
    resolved_handles: dict[str, str] = {}

    for tweet in tweets:
        post = _build_post_from_tweet(tweet)
        thread_id = str(getattr(tweet, "conversationId", None) or post.post_id)
        grouped_posts.setdefault(thread_id, []).append(post)
        resolved_handles[thread_id] = post.author_handle or account_handle

    threads = [
        Thread(
            thread_id=thread_id,
            account_handle=resolved_handles[thread_id],
            posts=sorted(posts, key=lambda post: post.created_at),
        )
        for thread_id, posts in grouped_posts.items()
    ]
    return sorted(threads, key=lambda thread: thread.primary_post.created_at)


def _iter_handle_batches(handles: list[str], batch_size: int):
    for index in range(0, len(handles), batch_size):
        yield handles[index : index + batch_size]


async def _fetch_threads_for_handle_with_retry(
    *,
    handle: str,
    fetch_threads_for_handle,
    max_handle_retries: int,
    handle_timeout_seconds: float,
):  # noqa: ANN001
    for attempt in range(max_handle_retries + 1):
        try:
            async with asyncio.timeout(handle_timeout_seconds):
                return await fetch_threads_for_handle(handle)
        except TimeoutError as error:
            if attempt == max_handle_retries:
                raise RuntimeError(
                    f"@{handle} timed out after {handle_timeout_seconds} seconds."
                ) from error
        except Exception as error:
            if attempt == max_handle_retries:
                raise RuntimeError(f"@{handle} failed: {error}") from error

    raise RuntimeError(f"@{handle} failed without returning threads.")


def _choose_failed_handle_action(*, failed_handles: list[str], input_fn, output_fn) -> str:  # noqa: ANN001
    output_fn(
        "Handles still failing after retries: "
        + ", ".join(f"@{handle}" for handle in failed_handles)
    )

    while True:
        try:
            response = input_fn(
                "Choose one action: retry, go on, or stop: "
            ).strip().lower()
        except EOFError as error:
            raise RuntimeError("Input closed while fetching handles.") from error

        if response in {"retry", "r"}:
            return "retry"
        if response in {"go on", "go", "g"}:
            return "go on"
        if response in {"stop", "s"}:
            return "stop"

        output_fn("Please answer with retry, go on, or stop.")


async def _fetch_threads_for_handles_in_batches(
    *,
    handles: list[str],
    fetch_threads_for_handle,
    batch_size: int,
    max_handle_retries: int,
    handle_timeout_seconds: float,
    input_fn=input,
    output_fn=print,
):  # noqa: ANN001
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")
    if max_handle_retries < 0:
        raise ValueError("max_handle_retries cannot be negative.")
    if handle_timeout_seconds <= 0:
        raise ValueError("handle_timeout_seconds must be positive.")

    all_threads: list[Thread] = []
    total_batches = max(1, (len(handles) + batch_size - 1) // batch_size)

    for batch_index, batch_handles in enumerate(_iter_handle_batches(handles, batch_size), start=1):
        output_fn(
            f"Fetching handle batch {batch_index}/{total_batches} "
            f"({len(batch_handles)} handles)."
        )
        pending_handles = list(batch_handles)

        while pending_handles:
            results = await asyncio.gather(
                *[
                    _fetch_threads_for_handle_with_retry(
                        handle=handle,
                        fetch_threads_for_handle=fetch_threads_for_handle,
                        max_handle_retries=max_handle_retries,
                        handle_timeout_seconds=handle_timeout_seconds,
                    )
                    for handle in pending_handles
                ],
                return_exceptions=True,
            )

            failed_handles: list[str] = []
            for handle, result in zip(pending_handles, results, strict=True):
                if isinstance(result, Exception):
                    output_fn(str(result))
                    failed_handles.append(handle)
                    continue
                all_threads.extend(result)

            if not failed_handles:
                break

            action = _choose_failed_handle_action(
                failed_handles=failed_handles,
                input_fn=input_fn,
                output_fn=output_fn,
            )
            if action == "retry":
                pending_handles = failed_handles
                continue
            if action == "go on":
                break
            raise RuntimeError("Stopped while fetching handles.")

    return sorted(all_threads, key=lambda thread: thread.primary_post.created_at)


async def _ensure_guest_token(account: Account, *, save_account) -> None:  # noqa: ANN001
    if account.headers.get("x-guest-token"):
        return

    async with account.make_client(proxy=account.proxy) as client:
        guest_token = await get_guest_token(client)

    account.headers["x-guest-token"] = guest_token
    if "ct0" in account.cookies:
        account.headers["x-csrf-token"] = account.cookies["ct0"]
    await save_account(account)


async def _bootstrap_cookie_account(api: API) -> Account:
    cookies = resolve_twitter_cookies()
    username = _build_cookie_account_name(cookies)
    await api.pool.add_account(
        username=username,
        password="",
        email="",
        email_password="",
        cookies=cookies,
    )
    account = await api.pool.get(username)
    if account is None:
        raise RuntimeError("twscrape cookie bootstrap did not create an account.")
    await _ensure_guest_token(account, save_account=api.pool.save)
    return account


async def ensure_twscrape_account(api: API) -> Account:
    accounts_info = await api.pool.accounts_info()
    for item in accounts_info:
        if not item["active"]:
            continue
        account = await api.pool.get(item["username"])
        if account is None:
            raise RuntimeError("twscrape reported an active account, but none could be loaded.")
        await _ensure_guest_token(account, save_account=api.pool.save)
        return account

    return await _bootstrap_cookie_account(api)


async def _get_twscrape_threads_async(handles: list[str], since_date) -> list[Thread]:  # noqa: ANN001
    db_file = _get_twscrape_db_file()
    db_file.parent.mkdir(parents=True, exist_ok=True)
    api = API(str(db_file))
    await ensure_twscrape_account(api)

    async def fetch_threads_for_handle(handle: str) -> list[Thread]:
        user = await api.user_by_login(handle)
        if user is None:
            return []

        tweets = []
        async for tweet in api.user_tweets(user.id, limit=40):
            created_at = getattr(tweet, "date", None)
            if created_at is None or created_at < since_date:
                continue
            tweets.append(tweet)

        return build_threads_from_tweets(handle, tweets)

    return await _fetch_threads_for_handles_in_batches(
        handles=handles,
        fetch_threads_for_handle=fetch_threads_for_handle,
        batch_size=DEFAULT_HANDLE_BATCH_SIZE,
        max_handle_retries=DEFAULT_MAX_HANDLE_RETRIES,
        handle_timeout_seconds=DEFAULT_HANDLE_TIMEOUT_SECONDS,
    )


def get_twscrape_threads(*, handles: list[str], since_date) -> list[Thread]:  # noqa: ANN001
    return asyncio.run(_get_twscrape_threads_async(handles, since_date))

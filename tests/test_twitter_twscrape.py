from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from xs2n.agents.schemas import Post, Thread
import xs2n.twitter_twscrape as twitter_twscrape


def test_get_twscrape_state_dir_defaults_to_user_home(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv(twitter_twscrape.TWSCRAPE_STATE_DIR_ENV_VAR, raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert twitter_twscrape.get_twscrape_state_dir() == (
        tmp_path / "Library" / "Application Support" / "xs2n" / "twscrape"
    )


def test_get_twscrape_state_dir_honors_env_override(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    custom_path = tmp_path / "custom"
    monkeypatch.setenv(twitter_twscrape.TWSCRAPE_STATE_DIR_ENV_VAR, str(custom_path))

    assert twitter_twscrape.get_twscrape_state_dir() == custom_path


def test_build_threads_from_tweets_groups_by_conversation_id() -> None:
    tweets = [
        SimpleNamespace(
            id=1,
            conversationId=10,
            date=datetime(2026, 3, 29, 10, 0, tzinfo=UTC),
            rawContent="first",
            url="https://x.com/alice/status/1",
            user=SimpleNamespace(username="alice"),
        ),
        SimpleNamespace(
            id=2,
            conversationId=10,
            date=datetime(2026, 3, 29, 10, 5, tzinfo=UTC),
            rawContent="second",
            url="https://x.com/alice/status/2",
            user=SimpleNamespace(username="alice"),
        ),
    ]

    threads = twitter_twscrape.build_threads_from_tweets("alice", tweets)

    assert len(threads) == 1
    assert threads[0].thread_id == "10"
    assert [post.post_id for post in threads[0].posts] == ["1", "2"]


def test_cookie_map_from_httpx_cookies_supports_cookie_jar() -> None:
    cookies = SimpleNamespace(
        jar=[
            SimpleNamespace(name="auth_token", value="token"),
            SimpleNamespace(name="ct0", value="csrf"),
        ]
    )

    assert twitter_twscrape.cookie_map_from_httpx_cookies(cookies) == {
        "auth_token": "token",
        "ct0": "csrf",
    }


def test_get_rate_limit_wait_seconds_prefers_reset_header() -> None:
    response = SimpleNamespace(headers={"x-rate-limit-reset": "111"})

    assert (
        twitter_twscrape.get_rate_limit_wait_seconds(response, current_time=lambda: 100.0) == 12
    )


def test_get_with_rate_limit_retry_retries_after_429() -> None:
    calls = {"count": 0, "slept": []}

    class FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str] | None = None) -> None:
            self.status_code = status_code
            self.headers = headers or {}

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

    class FakeClient:
        async def get(self, url: str, params):  # noqa: ANN001
            calls["count"] += 1
            if calls["count"] == 1:
                return FakeResponse(429, {"retry-after": "1"})
            return FakeResponse(200)

    async def fake_sleep(seconds: int) -> None:
        calls["slept"].append(seconds)

    asyncio.run(
        twitter_twscrape.get_with_rate_limit_retry(
            FakeClient(),
            "https://example.com",
            params={},
            sleep=fake_sleep,
        )
    )

    assert calls == {"count": 2, "slept": [1]}


def test_ensure_twscrape_account_reuses_existing_active_state(monkeypatch) -> None:  # noqa: ANN001
    account = SimpleNamespace(
        username="saved",
        headers={"x-guest-token": "guest"},
        cookies={"ct0": "csrf"},
        proxy=None,
    )
    api = SimpleNamespace(
        pool=SimpleNamespace(
            accounts_info=lambda: _awaitable([{"username": "saved", "active": True}]),
            get=lambda username: _awaitable(account if username == "saved" else None),
            save=lambda item: _awaitable(item),
        )
    )

    result = asyncio.run(twitter_twscrape.ensure_twscrape_account(api))

    assert result is account


def test_ensure_twscrape_account_bootstraps_cookie_account_when_state_is_empty(monkeypatch) -> None:  # noqa: ANN001
    account = SimpleNamespace(
        username="cookie",
        headers={"x-guest-token": "guest"},
        cookies={"ct0": "csrf"},
        proxy=None,
    )
    calls: dict[str, object] = {}

    async def add_account(**kwargs):  # noqa: ANN003
        calls["add_account"] = kwargs

    api = SimpleNamespace(
        pool=SimpleNamespace(
            accounts_info=lambda: _awaitable([]),
            add_account=add_account,
            get=lambda username: _awaitable(account if username.startswith("xs2n-cookie-") else None),
            save=lambda item: _awaitable(item),
        )
    )
    monkeypatch.setattr(twitter_twscrape, "resolve_twitter_cookies", lambda: "auth_token=a; ct0=b")

    result = asyncio.run(twitter_twscrape.ensure_twscrape_account(api))

    assert result is account
    assert calls["add_account"]["cookies"] == "auth_token=a; ct0=b"


def test_fetch_threads_for_handles_in_batches_retries_failed_handles_after_prompt() -> None:
    attempts = {"alice": 0, "bob": 0, "carl": 0}
    prompts: list[str] = []

    async def fake_fetch_threads_for_handle(handle: str) -> list[Thread]:
        attempts[handle] += 1
        if handle == "bob" and attempts[handle] < 3:
            raise RuntimeError("temporary failure")
        return [_build_thread(handle)]

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return "retry"

    threads = asyncio.run(
        twitter_twscrape._fetch_threads_for_handles_in_batches(
            handles=["alice", "bob", "carl"],
            fetch_threads_for_handle=fake_fetch_threads_for_handle,
            batch_size=2,
            max_handle_retries=1,
            handle_timeout_seconds=5.0,
            input_fn=fake_input,
            output_fn=lambda message: None,
        )
    )

    assert [thread.account_handle for thread in threads] == ["alice", "bob", "carl"]
    assert attempts == {"alice": 1, "bob": 3, "carl": 1}
    assert prompts == ["Choose one action: retry, go on, or stop: "]


def test_fetch_threads_for_handles_in_batches_can_go_on_after_failures() -> None:
    prompts: list[str] = []

    async def fake_fetch_threads_for_handle(handle: str) -> list[Thread]:
        if handle == "bob":
            raise RuntimeError("still failing")
        return [_build_thread(handle)]

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return "go on"

    threads = asyncio.run(
        twitter_twscrape._fetch_threads_for_handles_in_batches(
            handles=["alice", "bob", "carl"],
            fetch_threads_for_handle=fake_fetch_threads_for_handle,
            batch_size=2,
            max_handle_retries=0,
            handle_timeout_seconds=5.0,
            input_fn=fake_input,
            output_fn=lambda message: None,
        )
    )

    assert [thread.account_handle for thread in threads] == ["alice", "carl"]
    assert len(prompts) == 1


def test_fetch_threads_for_handles_in_batches_stops_when_user_requests_stop() -> None:
    async def fake_fetch_threads_for_handle(handle: str) -> list[Thread]:
        raise RuntimeError(f"{handle} failed")

    with pytest.raises(RuntimeError, match="Stopped while fetching handles"):
        asyncio.run(
            twitter_twscrape._fetch_threads_for_handles_in_batches(
                handles=["alice"],
                fetch_threads_for_handle=fake_fetch_threads_for_handle,
                batch_size=1,
                max_handle_retries=0,
                handle_timeout_seconds=5.0,
                input_fn=lambda prompt: "stop",
                output_fn=lambda message: None,
            )
        )


def test_fetch_threads_for_handles_in_batches_treats_timeout_as_failed_handle() -> None:
    prompts: list[str] = []

    async def fake_fetch_threads_for_handle(handle: str) -> list[Thread]:
        await asyncio.sleep(0.05)
        return [_build_thread(handle)]

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return "go on"

    threads = asyncio.run(
        twitter_twscrape._fetch_threads_for_handles_in_batches(
            handles=["slow"],
            fetch_threads_for_handle=fake_fetch_threads_for_handle,
            batch_size=1,
            max_handle_retries=0,
            handle_timeout_seconds=0.01,
            input_fn=fake_input,
            output_fn=lambda message: None,
        )
    )

    assert threads == []
    assert len(prompts) == 1


def _build_thread(handle: str) -> Thread:
    return Thread(
        thread_id=f"{handle}-thread",
        account_handle=handle,
        posts=[
            Post(
                post_id=f"{handle}-post",
                author_handle=handle,
                created_at=datetime(2026, 3, 29, 10, 0, tzinfo=UTC),
                text=f"{handle} post",
                url=f"https://x.com/{handle}/status/{handle}-post",
            )
        ],
    )


def _awaitable(value):  # noqa: ANN001, ANN202
    async def _inner():
        return value

    return _inner()

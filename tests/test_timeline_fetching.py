from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from xs2n.profile.timeline import (
    AUTHENTICATED_ACCOUNT_SENTINEL,
    import_timeline_entries,
)


class _DummyUserRef:
    def __init__(self, screen_name: str) -> None:
        self.screen_name = screen_name


class _DummyTweet:
    def __init__(
        self,
        *,
        tweet_id: str,
        created_at_datetime: datetime | None,
        created_at: str,
        text: str,
        author_handle: str,
        retweeted_tweet: "_DummyTweet | None" = None,
        in_reply_to: str | None = None,
    ) -> None:
        self.id = tweet_id
        self.created_at_datetime = created_at_datetime
        self.created_at = created_at
        self.text = text
        self.full_text = text
        self.user = _DummyUserRef(author_handle)
        self.retweeted_tweet = retweeted_tweet
        self.in_reply_to = in_reply_to


class _DummyBatch(list):
    def __init__(self, items: list[_DummyTweet], next_batch: "_DummyBatch | None" = None) -> None:
        super().__init__(items)
        self._next_batch = next_batch

    async def next(self):  # noqa: ANN201
        if self._next_batch is None:
            return _DummyBatch([])
        return self._next_batch


class _DummyUser:
    def __init__(self, screen_name: str, first_batch: _DummyBatch) -> None:
        self.screen_name = screen_name
        self.first_batch = first_batch
        self.get_tweets_calls: list[tuple[str, int]] = []

    async def get_tweets(self, tweet_type: str, count: int):  # noqa: ANN201
        self.get_tweets_calls.append((tweet_type, count))
        return self.first_batch


class _DummyClient:
    def __init__(self, locale: str, user: _DummyUser) -> None:
        self.locale = locale
        self._user = user
        self.user_called = False
        self.by_name_calls: list[str] = []

    async def user(self) -> _DummyUser:
        self.user_called = True
        return self._user

    async def get_user_by_screen_name(self, screen_name: str) -> _DummyUser:
        self.by_name_calls.append(screen_name)
        return self._user


def _tweet(
    tweet_id: str,
    created_at_datetime: datetime | None,
    *,
    author: str = "mx",
    text: str = "hello",
    retweeted_tweet: _DummyTweet | None = None,
    in_reply_to: str | None = None,
) -> _DummyTweet:
    fallback_created_at = (
        created_at_datetime or datetime(2026, 1, 1, tzinfo=timezone.utc)
    ).strftime("%a %b %d %H:%M:%S %z %Y")
    return _DummyTweet(
        tweet_id=tweet_id,
        created_at_datetime=created_at_datetime,
        created_at=fallback_created_at,
        text=text,
        author_handle=author,
        retweeted_tweet=retweeted_tweet,
        in_reply_to=in_reply_to,
    )


def test_import_timeline_entries_filters_since_and_classifies_retweets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    original = _tweet(
        "orig",
        datetime(2025, 12, 25, tzinfo=timezone.utc),
        author="other",
        text="original",
    )
    page_2 = _DummyBatch(
        [
            _tweet("old", datetime(2025, 12, 30, tzinfo=timezone.utc), text="too old"),
            _tweet("reply", datetime(2026, 1, 2, tzinfo=timezone.utc), in_reply_to="1"),
        ]
    )
    page_1 = _DummyBatch(
        [
            _tweet("1", datetime(2026, 1, 3, tzinfo=timezone.utc), text="post"),
            _tweet(
                "2",
                datetime(2026, 1, 2, tzinfo=timezone.utc),
                text="retweet event",
                retweeted_tweet=original,
            ),
        ],
        next_batch=page_2,
    )
    dummy_user = _DummyUser(screen_name="mx", first_batch=page_1)

    holder: dict[str, _DummyClient] = {}

    def fake_client(locale: str) -> _DummyClient:
        client = _DummyClient(locale=locale, user=dummy_user)
        holder["client"] = client
        return client

    async def fake_ensure_authenticated_client(**kwargs):  # noqa: ANN202
        return None

    monkeypatch.setattr("xs2n.profile.timeline.Client", fake_client)
    monkeypatch.setattr(
        "xs2n.profile.timeline.ensure_authenticated_client",
        fake_ensure_authenticated_client,
    )

    result = asyncio.run(
        import_timeline_entries(
            account_screen_name="mx",
            cookies_file=Path("cookies.json"),
            since_datetime=since,
            limit=10,
            prompt_login=lambda *_: ("u", "e", "p"),
        )
    )

    assert [entry.tweet_id for entry in result.entries] == ["1", "2"]
    assert [entry.kind for entry in result.entries] == ["post", "retweet"]
    assert result.skipped_old == 1
    assert result.scanned == 4

    client = holder["client"]
    assert client.by_name_calls == ["mx"]
    assert client.user_called is False
    assert dummy_user.get_tweets_calls == [("Tweets", 10)]


def test_import_timeline_entries_uses_self_account_and_created_at_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    tweet = _DummyTweet(
        tweet_id="fallback",
        created_at_datetime=None,
        created_at="Mon Jan 05 10:00:00 +0000 2026",
        text="fallback date",
        author_handle="self_handle",
    )
    batch = _DummyBatch([tweet])
    dummy_user = _DummyUser(screen_name="self_handle", first_batch=batch)
    holder: dict[str, _DummyClient] = {}

    def fake_client(locale: str) -> _DummyClient:
        client = _DummyClient(locale=locale, user=dummy_user)
        holder["client"] = client
        return client

    async def fake_ensure_authenticated_client(**kwargs):  # noqa: ANN202
        return None

    monkeypatch.setattr("xs2n.profile.timeline.Client", fake_client)
    monkeypatch.setattr(
        "xs2n.profile.timeline.ensure_authenticated_client",
        fake_ensure_authenticated_client,
    )

    result = asyncio.run(
        import_timeline_entries(
            account_screen_name=AUTHENTICATED_ACCOUNT_SENTINEL,
            cookies_file=Path("cookies.json"),
            since_datetime=since,
            limit=5,
            prompt_login=lambda *_: ("u", "e", "p"),
        )
    )

    client = holder["client"]
    assert client.user_called is True
    assert client.by_name_calls == []
    assert len(result.entries) == 1
    assert result.entries[0].account_handle == "self_handle"
    assert result.entries[0].tweet_id == "fallback"


def test_import_timeline_entries_applies_page_delay_between_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    page_2 = _DummyBatch(
        [
            _tweet("2", datetime(2026, 1, 2, tzinfo=timezone.utc), text="second page"),
        ]
    )
    page_1 = _DummyBatch(
        [
            _tweet("1", datetime(2026, 1, 3, tzinfo=timezone.utc), text="first page"),
        ],
        next_batch=page_2,
    )
    dummy_user = _DummyUser(screen_name="mx", first_batch=page_1)

    def fake_client(locale: str) -> _DummyClient:
        return _DummyClient(locale=locale, user=dummy_user)

    async def fake_ensure_authenticated_client(**kwargs):  # noqa: ANN202
        return None

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr("xs2n.profile.timeline.Client", fake_client)
    monkeypatch.setattr(
        "xs2n.profile.timeline.ensure_authenticated_client",
        fake_ensure_authenticated_client,
    )
    monkeypatch.setattr("xs2n.profile.timeline.asyncio.sleep", fake_sleep)

    asyncio.run(
        import_timeline_entries(
            account_screen_name="mx",
            cookies_file=Path("cookies.json"),
            since_datetime=since,
            limit=10,
            prompt_login=lambda *_: ("u", "e", "p"),
            page_delay_seconds=0.5,
        )
    )

    assert sleep_calls
    assert all(call == 0.5 for call in sleep_calls)

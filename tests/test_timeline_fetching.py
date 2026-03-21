from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest
from twikit.errors import NotFound

from xs2n.profile.timeline import (
    AUTHENTICATED_ACCOUNT_SENTINEL,
    import_home_latest_timeline_entries,
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
        conversation_id: str | None = None,
        legacy_conversation_id: str | None = None,
        replies: "_DummyBatch | None" = None,
        favorite_count: int | None = None,
        retweet_count: int | None = None,
        reply_count: int | None = None,
        quote_count: int | None = None,
        view_count: int | None = None,
    ) -> None:
        self.id = tweet_id
        self.created_at_datetime = created_at_datetime
        self.created_at = created_at
        self.text = text
        self.full_text = text
        self.user = _DummyUserRef(author_handle)
        self.retweeted_tweet = retweeted_tweet
        self.in_reply_to = in_reply_to
        self.conversation_id = conversation_id
        self._legacy: dict[str, str] = {}
        if legacy_conversation_id is not None:
            self._legacy["conversation_id_str"] = legacy_conversation_id
        self.replies = replies
        self.favorite_count = favorite_count
        self.retweet_count = retweet_count
        self.reply_count = reply_count
        self.quote_count = quote_count
        self.view_count = view_count


class _DummyBatch(list):
    def __init__(self, items: list[_DummyTweet], next_batch: "_DummyBatch | None" = None) -> None:
        super().__init__(items)
        self._next_batch = next_batch

    async def next(self):  # noqa: ANN201
        if self._next_batch is None:
            return _DummyBatch([])
        return self._next_batch


class _DummyUser:
    def __init__(
        self,
        screen_name: str,
        tweets_batch: _DummyBatch,
        replies_batch: _DummyBatch | None = None,
    ) -> None:
        self.screen_name = screen_name
        self._batches = {"Tweets": tweets_batch, "Replies": replies_batch or _DummyBatch([])}
        self.get_tweets_calls: list[tuple[str, int]] = []

    async def get_tweets(self, tweet_type: str, count: int):  # noqa: ANN201
        self.get_tweets_calls.append((tweet_type, count))
        return self._batches.get(tweet_type, _DummyBatch([]))


class _DummyClient:
    def __init__(
        self,
        locale: str,
        user: _DummyUser,
        tweet_details: dict[str, _DummyTweet] | None = None,
        home_latest_batch: _DummyBatch | None = None,
    ) -> None:
        self.locale = locale
        self._user = user
        self._tweet_details = tweet_details or {}
        self._home_latest_batch = home_latest_batch or _DummyBatch([])
        self.user_called = False
        self.by_name_calls: list[str] = []
        self.detail_calls: list[str] = []
        self.home_latest_calls: list[tuple[int, list[str] | None, str | None]] = []

    async def user(self) -> _DummyUser:
        self.user_called = True
        return self._user

    async def get_user_by_screen_name(self, screen_name: str) -> _DummyUser:
        self.by_name_calls.append(screen_name)
        return self._user

    async def get_tweet_by_id(self, tweet_id: str) -> _DummyTweet:
        self.detail_calls.append(tweet_id)
        if tweet_id not in self._tweet_details:
            raise NotFound(f"tweet {tweet_id} not found")
        return self._tweet_details[tweet_id]

    async def get_latest_timeline(
        self,
        count: int = 20,
        seen_tweet_ids: list[str] | None = None,
        cursor: str | None = None,
    ) -> _DummyBatch:
        self.home_latest_calls.append((count, seen_tweet_ids, cursor))
        return self._home_latest_batch


def _tweet(
    tweet_id: str,
    created_at_datetime: datetime | None,
    *,
    author: str = "mx",
    text: str = "hello",
    retweeted_tweet: _DummyTweet | None = None,
    in_reply_to: str | None = None,
    conversation_id: str | None = None,
    legacy_conversation_id: str | None = None,
    replies: _DummyBatch | None = None,
    favorite_count: int | None = None,
    retweet_count: int | None = None,
    reply_count: int | None = None,
    quote_count: int | None = None,
    view_count: int | None = None,
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
        conversation_id=conversation_id,
        legacy_conversation_id=legacy_conversation_id,
        replies=replies,
        favorite_count=favorite_count,
        retweet_count=retweet_count,
        reply_count=reply_count,
        quote_count=quote_count,
        view_count=view_count,
    )


def test_import_timeline_entries_includes_replies_and_classifies_kinds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    original = _tweet(
        "orig",
        datetime(2025, 12, 25, tzinfo=timezone.utc),
        author="other",
        text="original",
    )
    tweets_batch = _DummyBatch(
        [
            _tweet("old", datetime(2025, 12, 30, tzinfo=timezone.utc), text="too old"),
            _tweet("1", datetime(2026, 1, 3, tzinfo=timezone.utc), text="post"),
            _tweet(
                "2",
                datetime(2026, 1, 2, tzinfo=timezone.utc),
                text="retweet event",
                retweeted_tweet=original,
            ),
        ]
    )
    replies_batch = _DummyBatch(
        [
            _tweet(
                "3",
                datetime(2026, 1, 2, 1, tzinfo=timezone.utc),
                text="thread reply",
                in_reply_to="1",
                conversation_id="conv-1",
            ),
            _tweet(
                "4",
                datetime(2026, 1, 2, 2, tzinfo=timezone.utc),
                text="legacy conversation id",
                in_reply_to="3",
                legacy_conversation_id="conv-1",
            ),
        ],
    )
    dummy_user = _DummyUser(
        screen_name="mx",
        tweets_batch=tweets_batch,
        replies_batch=replies_batch,
    )

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
            thread_parent_limit=0,
            thread_replies_limit=0,
            thread_other_replies_limit=0,
        )
    )

    assert [entry.tweet_id for entry in result.entries] == ["1", "4", "3", "2"]
    assert [entry.kind for entry in result.entries] == ["post", "reply", "reply", "retweet"]
    reply = next(entry for entry in result.entries if entry.tweet_id == "3")
    legacy_reply = next(entry for entry in result.entries if entry.tweet_id == "4")
    assert reply.in_reply_to_tweet_id == "1"
    assert reply.conversation_id == "conv-1"
    assert reply.timeline_source == "replies"
    assert legacy_reply.conversation_id == "conv-1"
    assert result.skipped_old == 1
    assert result.scanned == 5

    client = holder["client"]
    assert client.by_name_calls == ["mx"]
    assert client.user_called is False
    assert dummy_user.get_tweets_calls == [("Tweets", 10), ("Replies", 10)]


def test_import_home_latest_timeline_entries_uses_author_as_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    original = _tweet(
        "orig",
        datetime(2025, 12, 30, tzinfo=timezone.utc),
        author="other",
        text="orig",
    )
    page_2 = _DummyBatch(
        [
            _tweet(
                "3",
                datetime(2026, 1, 2, tzinfo=timezone.utc),
                author="gamma",
                text="reply",
                in_reply_to="1",
                conversation_id="conv-1",
            ),
            _tweet("old", datetime(2025, 12, 31, tzinfo=timezone.utc), author="delta"),
        ]
    )
    page_1 = _DummyBatch(
        [
            _tweet("1", datetime(2026, 1, 4, tzinfo=timezone.utc), author="alpha", text="post"),
            _tweet(
                "2",
                datetime(2026, 1, 3, tzinfo=timezone.utc),
                author="beta",
                text="retweet",
                retweeted_tweet=original,
            ),
        ],
        next_batch=page_2,
    )
    dummy_user = _DummyUser(screen_name="mx", tweets_batch=_DummyBatch([]))
    holder: dict[str, _DummyClient] = {}

    def fake_client(locale: str) -> _DummyClient:
        client = _DummyClient(
            locale=locale,
            user=dummy_user,
            home_latest_batch=page_1,
        )
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
        import_home_latest_timeline_entries(
            cookies_file=Path("cookies.json"),
            since_datetime=since,
            limit=3,
            prompt_login=lambda *_: ("u", "e", "p"),
            page_delay_seconds=0.0,
        )
    )

    assert [entry.tweet_id for entry in result.entries] == ["1", "2", "3"]
    assert [entry.kind for entry in result.entries] == ["post", "retweet", "reply"]
    assert all(entry.timeline_source == "home_latest" for entry in result.entries)
    assert all(entry.account_handle == entry.author_handle for entry in result.entries)
    assert result.scanned == 3
    assert result.skipped_old == 0

    client = holder["client"]
    assert client.home_latest_calls == [(3, None, None)]


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
    dummy_user = _DummyUser(screen_name="self_handle", tweets_batch=batch)
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
            thread_parent_limit=0,
            thread_replies_limit=0,
            thread_other_replies_limit=0,
        )
    )

    client = holder["client"]
    assert client.user_called is True
    assert client.by_name_calls == []
    assert len(result.entries) == 1
    assert result.entries[0].account_handle == "self_handle"
    assert result.entries[0].tweet_id == "fallback"


def test_import_timeline_entries_captures_engagement_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    tweet = _tweet(
        "metrics",
        datetime(2026, 1, 5, tzinfo=timezone.utc),
        text="metrics",
        favorite_count=101,
        retweet_count=12,
        reply_count=7,
        quote_count=4,
        view_count=9090,
    )
    batch = _DummyBatch([tweet])
    dummy_user = _DummyUser(screen_name="mx", tweets_batch=batch)

    def fake_client(locale: str) -> _DummyClient:
        return _DummyClient(locale=locale, user=dummy_user)

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
            thread_parent_limit=0,
            thread_replies_limit=0,
            thread_other_replies_limit=0,
        )
    )

    entry = result.entries[0]
    assert entry.favorite_count == 101
    assert entry.retweet_count == 12
    assert entry.reply_count == 7
    assert entry.quote_count == 4
    assert entry.view_count == 9090


def test_import_timeline_entries_captures_media_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    tweet = _tweet(
        "media",
        datetime(2026, 1, 5, tzinfo=timezone.utc),
        text="post with media",
    )
    tweet._legacy["entities"] = {
        "media": [
            {
                "id_str": "photo-1",
                "media_url_https": "https://img.test/post.png",
                "type": "photo",
                "original_info": {"width": 1200, "height": 800},
            }
        ]
    }
    batch = _DummyBatch([tweet])
    dummy_user = _DummyUser(screen_name="mx", tweets_batch=batch)

    def fake_client(locale: str) -> _DummyClient:
        return _DummyClient(locale=locale, user=dummy_user)

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
            thread_parent_limit=0,
            thread_replies_limit=0,
            thread_other_replies_limit=0,
        )
    )

    entry = result.entries[0]
    assert entry.media == [
        {
            "media_url": "https://img.test/post.png",
            "media_type": "photo",
            "width": 1200,
            "height": 800,
        }
    ]


def test_import_timeline_entries_tolerates_unreadable_private_legacy_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BrokenLegacyTweet:
        def __init__(self) -> None:
            created_at = datetime(2026, 1, 5, tzinfo=timezone.utc)
            self.id = "broken-legacy"
            self.created_at_datetime = created_at
            self.created_at = created_at.strftime("%a %b %d %H:%M:%S %z %Y")
            self.text = "post with unreadable private payload"
            self.full_text = self.text
            self.user = _DummyUserRef("mx")
            self.retweeted_tweet = None
            self.in_reply_to = None
            self.conversation_id = None

        @property
        def _legacy(self) -> dict[str, object]:
            raise RuntimeError("private payload unavailable")

    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    batch = _DummyBatch([_BrokenLegacyTweet()])
    dummy_user = _DummyUser(screen_name="mx", tweets_batch=batch)

    def fake_client(locale: str) -> _DummyClient:
        return _DummyClient(locale=locale, user=dummy_user)

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
            thread_parent_limit=0,
            thread_replies_limit=0,
            thread_other_replies_limit=0,
        )
    )

    entry = result.entries[0]
    assert entry.tweet_id == "broken-legacy"
    assert entry.conversation_id is None
    assert entry.media == []


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
    dummy_user = _DummyUser(screen_name="mx", tweets_batch=page_1)

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
            thread_parent_limit=0,
            thread_replies_limit=0,
            thread_other_replies_limit=0,
        )
    )

    assert sleep_calls
    assert all(call == 0.5 for call in sleep_calls)


def test_import_timeline_entries_hydrates_parent_chain_with_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    child_reply = _tweet(
        "child",
        datetime(2026, 1, 3, tzinfo=timezone.utc),
        in_reply_to="parent-1",
        conversation_id="parent-1",
    )
    dummy_user = _DummyUser(
        screen_name="mx",
        tweets_batch=_DummyBatch([]),
        replies_batch=_DummyBatch([child_reply]),
    )

    tweet_details = {
        "parent-1": _tweet(
            "parent-1",
            datetime(2026, 1, 2, tzinfo=timezone.utc),
            author="other",
            in_reply_to="parent-2",
        ),
        "parent-2": _tweet(
            "parent-2",
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            author="other",
        ),
    }
    holder: dict[str, _DummyClient] = {}

    def fake_client(locale: str) -> _DummyClient:
        client = _DummyClient(locale=locale, user=dummy_user, tweet_details=tweet_details)
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
            thread_parent_limit=1,
            thread_replies_limit=0,
            thread_other_replies_limit=0,
        )
    )

    assert [entry.tweet_id for entry in result.entries] == ["child", "parent-1"]
    parent_entry = next(entry for entry in result.entries if entry.tweet_id == "parent-1")
    assert parent_entry.timeline_source == "thread_parent"
    assert holder["client"].detail_calls == ["parent-1"]


def test_import_timeline_entries_limits_other_author_recursive_replies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    root_tweet = _tweet("root", datetime(2026, 1, 3, tzinfo=timezone.utc), conversation_id="root")
    dummy_user = _DummyUser(screen_name="mx", tweets_batch=_DummyBatch([root_tweet]))

    reply_self = _tweet(
        "reply-self",
        datetime(2026, 1, 2, 3, tzinfo=timezone.utc),
        author="mx",
        in_reply_to="root",
        conversation_id="root",
    )
    reply_other = _tweet(
        "reply-other",
        datetime(2026, 1, 2, 2, tzinfo=timezone.utc),
        author="other",
        in_reply_to="root",
        conversation_id="root",
    )
    nested_other = _tweet(
        "nested-other",
        datetime(2026, 1, 2, 1, tzinfo=timezone.utc),
        author="other2",
        in_reply_to="reply-self",
        conversation_id="root",
    )

    tweet_details = {
        "root": _tweet(
            "root",
            datetime(2026, 1, 3, tzinfo=timezone.utc),
            author="mx",
            replies=_DummyBatch([reply_self, reply_other]),
        ),
        "reply-self": _tweet(
            "reply-self",
            datetime(2026, 1, 2, 3, tzinfo=timezone.utc),
            author="mx",
            in_reply_to="root",
            replies=_DummyBatch([nested_other]),
        ),
        "reply-other": _tweet(
            "reply-other",
            datetime(2026, 1, 2, 2, tzinfo=timezone.utc),
            author="other",
            in_reply_to="root",
            replies=_DummyBatch([]),
        ),
    }
    holder: dict[str, _DummyClient] = {}

    def fake_client(locale: str) -> _DummyClient:
        client = _DummyClient(locale=locale, user=dummy_user, tweet_details=tweet_details)
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
            thread_parent_limit=0,
            thread_replies_limit=3,
            thread_other_replies_limit=1,
        )
    )

    thread_replies = [entry for entry in result.entries if entry.timeline_source == "thread_reply"]
    other_thread_replies = [entry for entry in thread_replies if entry.author_handle != "mx"]
    assert [entry.tweet_id for entry in thread_replies] == ["reply-self", "reply-other"]
    assert len(other_thread_replies) == 1
    assert "root" in holder["client"].detail_calls
    assert "reply-self" in holder["client"].detail_calls

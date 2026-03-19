from __future__ import annotations

from xs2n.schemas.digest import Issue, IssueThread
from xs2n.ui.digest_browser_state import DigestBrowserState
from xs2n.ui.saved_digest import SavedDigestPreview


def _preview() -> SavedDigestPreview:
    tweet = {
        "tweet_id": "2032245601216389324",
        "account_handle": "realmcore_",
        "author_handle": "realmcore_",
        "kind": "retweet",
        "created_at": "2026-03-13T00:01:23Z",
        "text": "Foundry capacity is still the gating factor for every major roadmap shift.",
        "conversation_id": "2032245601216389324",
        "favorite_count": 0,
        "retweet_count": 2,
        "reply_count": 0,
        "quote_count": 0,
        "view_count": None,
        "media": [],
    }
    issue_thread = IssueThread.model_validate(
        {
            "thread_id": "2032245601216389324",
            "conversation_id": "2032245601216389324",
            "account_handle": "realmcore_",
            "tweets": [tweet],
            "source_tweet_ids": ["2032245601216389324"],
            "context_tweet_ids": [],
            "latest_created_at": "2026-03-13T00:01:23Z",
            "primary_tweet_id": "2032245601216389324",
            "primary_tweet": tweet,
            "keep": True,
            "filter_reason": "High-signal infrastructure thread.",
            "issue_slug": "chip_race",
            "issue_title": "Chip Race",
            "issue_summary": "Supply constraints keep shaping AI infra.",
            "thread_title": "Foundry capacity is still the gating factor",
            "thread_summary": "A short report on why foundry capacity still drives the roadmap.",
            "why_this_thread_belongs": "It adds concrete evidence to the chip-capacity issue.",
        }
    )
    issue = Issue.model_validate(
        {
            "slug": "chip_race",
            "title": "Chip Race",
            "summary": "Supply constraints keep shaping AI infra.",
            "thread_ids": ["2032245601216389324"],
            "thread_count": 1,
        }
    )
    return SavedDigestPreview(
        run_id="20260318T225654Z",
        digest_title="Context Management for Agentic Systems",
        issues=[issue],
        issue_threads=[issue_thread],
    )


def test_digest_browser_state_opens_overview_by_default() -> None:
    state = DigestBrowserState(_preview())

    screen = state.current_screen()

    assert screen.mode == "overview"
    assert screen.title == "Context Management for Agentic Systems"
    assert screen.can_go_back is False
    assert screen.open_url is None
    assert [row.kind for row in screen.rows] == ["issue", "thread"]


def test_digest_browser_state_can_open_thread_and_go_back() -> None:
    state = DigestBrowserState(_preview())

    state.show_thread("2032245601216389324")
    thread_screen = state.current_screen()

    assert thread_screen.mode == "thread"
    assert thread_screen.can_go_back is True
    assert thread_screen.open_url == "https://x.com/realmcore_/status/2032245601216389324"
    assert "Digest / Chip Race / Foundry capacity is still the gating factor" in thread_screen.subtitle
    assert [row.kind for row in thread_screen.rows] == ["tweet"]

    state.go_back()
    overview_screen = state.current_screen()

    assert overview_screen.mode == "overview"
    assert overview_screen.can_go_back is False

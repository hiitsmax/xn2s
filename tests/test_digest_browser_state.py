from __future__ import annotations

from xs2n.schemas.digest import Issue, IssueThread
from xs2n.ui.digest_browser_state import DigestBrowserState
from xs2n.ui.saved_digest import SavedDigestPreview


def _preview() -> SavedDigestPreview:
    first_tweet = {
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
    second_tweet = {
        "tweet_id": "2032245601216389325",
        "account_handle": "realmcore_",
        "author_handle": "realmcore_",
        "kind": "reply",
        "created_at": "2026-03-13T00:11:23Z",
        "text": "The follow-up explains why advanced packaging is still the real bottleneck.",
        "conversation_id": "2032245601216389324",
        "favorite_count": 1,
        "retweet_count": 1,
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
            "tweets": [first_tweet, second_tweet],
            "source_tweet_ids": ["2032245601216389324", "2032245601216389325"],
            "context_tweet_ids": [],
            "latest_created_at": "2026-03-13T00:11:23Z",
            "primary_tweet_id": "2032245601216389324",
            "primary_tweet": first_tweet,
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
    second_issue_thread = IssueThread.model_validate(
        {
            "thread_id": "3032245601216389324",
            "conversation_id": "3032245601216389324",
            "account_handle": "agentic",
            "tweets": [
                {
                    "tweet_id": "3032245601216389324",
                    "account_handle": "agentic",
                    "author_handle": "agentic",
                    "kind": "post",
                    "created_at": "2026-03-13T01:01:23Z",
                    "text": "Context windows are not enough; retrieval quality decides the actual outcome.",
                    "conversation_id": "3032245601216389324",
                    "favorite_count": 0,
                    "retweet_count": 0,
                    "reply_count": 0,
                    "quote_count": 0,
                    "view_count": None,
                    "media": [],
                }
            ],
            "source_tweet_ids": ["3032245601216389324"],
            "context_tweet_ids": [],
            "latest_created_at": "2026-03-13T01:01:23Z",
            "primary_tweet_id": "3032245601216389324",
            "primary_tweet": {
                "tweet_id": "3032245601216389324",
                "account_handle": "agentic",
                "author_handle": "agentic",
                "kind": "post",
                "created_at": "2026-03-13T01:01:23Z",
                "text": "Context windows are not enough; retrieval quality decides the actual outcome.",
                "conversation_id": "3032245601216389324",
                "favorite_count": 0,
                "retweet_count": 0,
                "reply_count": 0,
                "quote_count": 0,
                "view_count": None,
                "media": [],
            },
            "keep": True,
            "filter_reason": "High-signal context-management thread.",
            "issue_slug": "context_systems",
            "issue_title": "Context Systems",
            "issue_summary": "Teams are moving from raw context windows to structured retrieval and memory.",
            "thread_title": "Context windows are not enough",
            "thread_summary": "A sharper claim that retrieval quality matters more than raw context length.",
            "why_this_thread_belongs": "It frames the architectural shift behind the issue.",
        }
    )
    return SavedDigestPreview(
        run_id="20260318T225654Z",
        digest_title="Context Management for Agentic Systems",
        issues=[
            Issue.model_validate(
                {
                    "slug": "chip_race",
                    "title": "Chip Race",
                    "summary": "Supply constraints keep shaping AI infra.",
                    "thread_ids": ["2032245601216389324"],
                    "thread_count": 1,
                }
            ),
            Issue.model_validate(
                {
                    "slug": "context_systems",
                    "title": "Context Systems",
                    "summary": "Teams are moving from raw context windows to structured retrieval and memory.",
                    "thread_ids": ["3032245601216389324"],
                    "thread_count": 1,
                }
            ),
        ],
        issue_threads=[issue_thread, second_issue_thread],
    )


def test_digest_browser_state_defaults_to_first_issue_without_thread_preview() -> None:
    state = DigestBrowserState(_preview())

    assert state.issue_rows()[0].slug == "chip_race"
    assert state.selected_issue().title == "Chip Race"
    assert state.selected_thread() is None
    assert [row.thread_id for row in state.thread_rows()] == ["2032245601216389324"]
    assert state.thread_preview() is None


def test_digest_browser_state_switches_issue_and_thread_preview() -> None:
    state = DigestBrowserState(_preview())

    state.select_issue("context_systems")

    assert state.selected_issue().title == "Context Systems"
    assert [row.thread_id for row in state.thread_rows()] == ["3032245601216389324"]
    assert state.thread_preview() is None

    state.select_thread("3032245601216389324")
    preview = state.thread_preview()

    assert preview is not None
    assert preview.open_url == "https://x.com/agentic/status/3032245601216389324"
    assert preview.issue_title == "Context Systems"
    assert len(preview.tweets) == 1

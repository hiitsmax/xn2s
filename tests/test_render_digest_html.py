from __future__ import annotations

from xs2n.agents.digest.steps.render_digest_html import run
from xs2n.schemas.digest import Issue, IssueThread


def test_render_digest_html_uses_simple_windows_classic_export() -> None:
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
    rendered = run(
        run_id="20260318T224700Z",
        digest_title="Chip Race",
        issues=[
            Issue.model_validate(
                {
                    "slug": "chip_race",
                    "title": "Chip Race",
                    "summary": "Supply constraints keep shaping AI infra.",
                    "thread_ids": ["2032245601216389324"],
                    "thread_count": 1,
                }
            )
        ],
        issue_threads=[
            IssueThread.model_validate(
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
        ],
    )

    assert "<!doctype html>" in rendered.lower()
    assert "Run 20260318T224700Z" in rendered
    assert "source 1" in rendered
    assert "#D4D0C8" in rendered
    assert "prefers-color-scheme" not in rendered
    assert '<main class="page">' not in rendered

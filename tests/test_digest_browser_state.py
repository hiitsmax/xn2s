from __future__ import annotations

from xs2n.schemas.digest import Issue, IssueThread
from xs2n.ui.digest_browser_preview import (
    build_issue_summary_panel,
    render_issue_canvas_styles,
    render_issue_canvas_text,
    render_issue_placeholder_text,
)
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
    followup_issue_thread = IssueThread.model_validate(
        {
            "thread_id": "2032245601216389399",
            "conversation_id": "2032245601216389399",
            "account_handle": "realmcore_",
            "tweets": [
                {
                    "tweet_id": "2032245601216389399",
                    "account_handle": "realmcore_",
                    "author_handle": "realmcore_",
                    "kind": "post",
                    "created_at": "2026-03-13T00:21:23Z",
                    "text": "Packaging constraints are now spilling directly into cloud roadmap timing.",
                    "conversation_id": "2032245601216389399",
                    "favorite_count": 3,
                    "retweet_count": 2,
                    "reply_count": 0,
                    "quote_count": 0,
                    "view_count": None,
                    "media": [],
                }
            ],
            "source_tweet_ids": ["2032245601216389399"],
            "context_tweet_ids": [],
            "latest_created_at": "2026-03-13T00:21:23Z",
            "primary_tweet_id": "2032245601216389399",
            "primary_tweet": {
                "tweet_id": "2032245601216389399",
                "account_handle": "realmcore_",
                "author_handle": "realmcore_",
                "kind": "post",
                "created_at": "2026-03-13T00:21:23Z",
                "text": "Packaging constraints are now spilling directly into cloud roadmap timing.",
                "conversation_id": "2032245601216389399",
                "favorite_count": 3,
                "retweet_count": 2,
                "reply_count": 0,
                "quote_count": 0,
                "view_count": None,
                "media": [],
            },
            "keep": True,
            "filter_reason": "Adds more evidence to the same supply-side issue.",
            "issue_slug": "chip_race",
            "issue_title": "Chip Race",
            "issue_summary": "Supply constraints keep shaping AI infra.",
            "thread_title": "Advanced packaging is turning into the next schedule risk",
            "thread_summary": "A follow-up note on why packaging now shifts deployment timing, not just manufacturing.",
            "why_this_thread_belongs": "It expands the issue from foundry supply to packaging bottlenecks.",
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
                    "thread_ids": [
                        "2032245601216389324",
                        "2032245601216389399",
                    ],
                    "thread_count": 2,
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
        issue_threads=[
            issue_thread,
            second_issue_thread,
            followup_issue_thread,
        ],
    )


def test_digest_browser_state_defaults_to_ranked_issue_preview() -> None:
    state = DigestBrowserState(_preview())
    issue_rows = state.issue_rows()
    preview = state.selected_issue_preview()

    assert [row.slug for row in issue_rows] == ["chip_race", "context_systems"]
    assert issue_rows[0].rank == 1
    assert issue_rows[0].thread_count == 2
    assert issue_rows[0].tweet_count == 3
    assert issue_rows[0].render_label() == "01\tTrack\t2T/3P\tChip Race"
    assert state.selected_issue().title == "Chip Race"
    assert state.digest_title == "Context Management for Agentic Systems"
    assert preview is not None
    assert preview.priority_rank == 1
    assert preview.thread_count == 2
    assert preview.tweet_count == 3
    assert preview.summary_meta() == "#01 Track | 2 threads | 3 posts"
    assert len(preview.threads) == 2
    assert preview.threads[0].thread_id == "2032245601216389324"
    assert preview.threads[1].thread_id == "2032245601216389399"


def test_digest_browser_state_switches_issue_preview() -> None:
    state = DigestBrowserState(_preview())

    state.select_issue("context_systems")

    preview = state.selected_issue_preview()

    assert state.selected_issue().title == "Context Systems"
    assert preview is not None
    assert preview.priority_rank == 2
    assert preview.lead_open_url == "https://x.com/agentic/status/3032245601216389324"
    assert preview.issue_title == "Context Systems"
    assert preview.thread_count == 1
    assert len(preview.threads) == 1
    assert preview.threads[0].tweet_count == 1


def test_render_issue_canvas_text_shows_all_threads_for_selected_issue() -> None:
    state = DigestBrowserState(_preview())

    rendered = render_issue_canvas_text(state.selected_issue_preview())

    assert "ISSUE:" not in rendered
    assert "Priority #01" not in rendered
    assert "Summary:" not in rendered
    assert "Why this matters:" not in rendered
    assert "Foundry capacity is still the gating factor" in rendered
    assert "Advanced packaging is turning into the next schedule risk" in rendered
    assert "Packaging constraints are now spilling directly into cloud roadmap timing." in rendered
    assert "@realmcore_" in rendered
    assert "It adds concrete evidence to the chip-capacity issue." in rendered
    assert "Supply constraints keep shaping AI infra." not in rendered
    assert (
        "01. Foundry capacity is still the gating factor\n\n"
        "A short report on why foundry capacity still drives the roadmap."
    ) in rendered


def test_render_issue_canvas_styles_give_titles_and_metadata_distinct_treatment() -> None:
    state = DigestBrowserState(_preview())
    rendered = render_issue_canvas_text(state.selected_issue_preview())
    styles = render_issue_canvas_styles(state.selected_issue_preview())

    title_index = rendered.index("01. Foundry capacity is still the gating factor")
    summary_index = rendered.index(
        "A short report on why foundry capacity still drives the roadmap."
    )
    why_index = rendered.index(
        "It adds concrete evidence to the chip-capacity issue."
    )
    tweet_meta_index = rendered.index("  01. @realmcore_ | retweet | 2026-03-13 00:01 UTC")
    tweet_text_index = rendered.index(
        "      Foundry capacity is still the gating factor for every major roadmap shift."
    )

    assert len(styles) == len(rendered)
    assert styles[title_index] == "B"
    assert styles[summary_index] == "C"
    assert styles[why_index] == "D"
    assert styles[tweet_meta_index] == "E"
    assert styles[tweet_text_index] == "F"


def test_render_issue_placeholder_text_guides_the_user() -> None:
    rendered = render_issue_placeholder_text(
        issue_title="Chip Race",
    )

    assert "Chip Race" in rendered
    assert "Issue overview" in rendered


def test_build_issue_summary_panel_keeps_secondary_column_compact() -> None:
    state = DigestBrowserState(_preview())

    panel = build_issue_summary_panel(state.selected_issue_preview())

    assert panel.title == "Chip Race"
    assert panel.meta == "#01 Track | 2 threads | 3 posts"
    assert panel.blurb == "Supply constraints keep shaping AI infra."


def test_digest_browser_state_uses_issue_title_when_run_title_is_missing() -> None:
    preview = _preview()
    preview.digest_title = None

    state = DigestBrowserState(preview)

    assert state.digest_title == "Chip Race"

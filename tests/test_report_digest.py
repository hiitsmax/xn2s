from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from xs2n.agents.digest import (
    AssemblyResult,
    CategorizationResult,
    ConversationCandidate,
    DEFAULT_TAXONOMY_DOC,
    FilteredUnit,
    IssueCluster,
    IssueClusterResult,
    SignalResult,
    ThreadState,
    TimelineRecord,
    _build_candidates,
    _select_report_records,
    _virality_score,
    run_digest_report,
)


class _FakeBackend:
    def assemble_conversation(self, *, taxonomy, candidate: ConversationCandidate) -> AssemblyResult:  # noqa: ANN001
        return AssemblyResult(
            title=f"Unit {candidate.unit_id}",
            summary="Combined thread view.",
            include_tweet_ids=[tweet.tweet_id for tweet in candidate.tweets],
            highlight_tweet_ids=[candidate.tweets[0].tweet_id],
            why_this_is_one_unit="The tweets form one conversation unit.",
        )

    def categorize_conversation(self, *, taxonomy, unit):  # noqa: ANN001, ANN201
        joined_text = " ".join(tweet.text.lower() for tweet in unit.tweets)
        if "promo" in joined_text:
            category = "promo"
        elif "debate" in joined_text:
            category = "debate"
        else:
            category = "analysis"
        return CategorizationResult(
            category=category,
            subcategory=None,
            editorial_angle="scaffold",
            reasoning="Deterministic test categorization.",
        )

    def extract_signal(self, *, taxonomy, unit: FilteredUnit) -> SignalResult:  # noqa: ANN001
        joined_text = " ".join(tweet.text.lower() for tweet in unit.tweets)
        disagreement = "debate" in joined_text
        return SignalResult(
            headline=unit.title,
            main_claim=unit.tweets[0].text,
            why_it_matters="This matters for the digest.",
            key_entities=[unit.account_handle],
            disagreement_present=disagreement,
            disagreement_summary="There is visible pushback." if disagreement else None,
            novelty_label="fresh",
            signal_score=81 if disagreement else 70,
        )

    def cluster_issues(self, *, taxonomy, units):  # noqa: ANN001, ANN201
        return IssueClusterResult(
            issues=[
                IssueCluster(
                    title="Main Topic",
                    summary="Grouped issue summary.",
                    unit_ids=[unit.unit_id for unit in units],
                )
            ]
        )


def _record(
    *,
    tweet_id: str,
    created_at: datetime,
    text: str,
    conversation_id: str | None = None,
    kind: str = "post",
    account_handle: str = "mx",
    author_handle: str = "mx",
    favorite_count: int = 0,
    retweet_count: int = 0,
    reply_count: int = 0,
    quote_count: int = 0,
    view_count: int = 0,
) -> TimelineRecord:
    return TimelineRecord.model_validate(
        {
            "tweet_id": tweet_id,
            "account_handle": account_handle,
            "author_handle": author_handle,
            "kind": kind,
            "created_at": created_at.isoformat(),
            "text": text,
            "conversation_id": conversation_id,
            "favorite_count": favorite_count,
            "retweet_count": retweet_count,
            "reply_count": reply_count,
            "quote_count": quote_count,
            "view_count": view_count,
        }
    )


def test_select_report_records_keeps_recent_and_heated_threads() -> None:
    now = datetime.now(timezone.utc)
    recent = _record(
        tweet_id="recent",
        created_at=now - timedelta(minutes=2),
        text="recent",
        conversation_id="conv-recent",
    )
    heated_old = _record(
        tweet_id="heated",
        created_at=now - timedelta(days=1),
        text="heated old",
        conversation_id="conv-heated",
    )
    ignored_old = _record(
        tweet_id="ignored",
        created_at=now - timedelta(days=2),
        text="ignored",
        conversation_id="conv-ignored",
    )
    previous_threads = {
        "conv-heated": ThreadState(
            title="Heated",
            heat_status="heated",
            momentum="rising",
            virality_score=10.0,
            disagreement_present=True,
            last_seen_at=now - timedelta(minutes=30),
        )
    }

    selected = _select_report_records(
        records=[recent, heated_old, ignored_old],
        previous_threads=previous_threads,
        fresh_cutoff=now - timedelta(minutes=10),
    )

    assert [record.tweet_id for record in selected] == ["recent", "heated"]


def test_build_candidates_uses_percentile_for_external_replies() -> None:
    now = datetime.now(timezone.utc)
    records = [
        _record(
            tweet_id="source",
            created_at=now - timedelta(minutes=5),
            text="thread root",
            conversation_id="conv-1",
            favorite_count=10,
        ),
        _record(
            tweet_id="reply-low",
            created_at=now - timedelta(minutes=4),
            text="small reply",
            conversation_id="conv-1",
            kind="reply",
            author_handle="other",
            favorite_count=3,
            retweet_count=1,
        ),
        _record(
            tweet_id="reply-high",
            created_at=now - timedelta(minutes=3),
            text="big reply",
            conversation_id="conv-1",
            kind="reply",
            author_handle="other",
            favorite_count=100,
            retweet_count=30,
            quote_count=10,
            view_count=10000,
        ),
    ]

    candidates = _build_candidates(records)

    assert len(candidates) == 1
    assert candidates[0].standout_reply_ids == ["reply-high"]


def test_virality_score_weights_multi_metric_signal() -> None:
    low = _record(
        tweet_id="low",
        created_at=datetime.now(timezone.utc),
        text="low",
        favorite_count=10,
        retweet_count=1,
        reply_count=1,
        quote_count=0,
        view_count=100,
    )
    high = _record(
        tweet_id="high",
        created_at=datetime.now(timezone.utc),
        text="high",
        favorite_count=100,
        retweet_count=20,
        reply_count=15,
        quote_count=8,
        view_count=10000,
    )

    assert _virality_score(high) > _virality_score(low)


def test_run_digest_report_writes_artifacts_and_updates_state(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    timeline_file = tmp_path / "timeline.json"
    taxonomy_file = tmp_path / "taxonomy.json"
    state_file = tmp_path / "report_state.json"
    output_dir = tmp_path / "report_runs"

    timeline_file.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "tweet_id": "fresh-1",
                        "account_handle": "mx",
                        "author_handle": "mx",
                        "kind": "post",
                        "created_at": (now - timedelta(minutes=5)).isoformat(),
                        "text": "A fresh debate is happening",
                        "conversation_id": "conv-fresh",
                        "favorite_count": 50,
                        "retweet_count": 8,
                        "reply_count": 6,
                        "quote_count": 2,
                        "view_count": 5000
                    },
                    {
                        "tweet_id": "fresh-2",
                        "account_handle": "mx",
                        "author_handle": "other",
                        "kind": "reply",
                        "created_at": (now - timedelta(minutes=4)).isoformat(),
                        "text": "debate reply",
                        "conversation_id": "conv-fresh",
                        "favorite_count": 120,
                        "retweet_count": 10,
                        "reply_count": 3,
                        "quote_count": 4,
                        "view_count": 9000
                    },
                    {
                        "tweet_id": "heated-1",
                        "account_handle": "mx",
                        "author_handle": "mx",
                        "kind": "post",
                        "created_at": (now - timedelta(days=1)).isoformat(),
                        "text": "Older tracked thread",
                        "conversation_id": "conv-heated",
                        "favorite_count": 80,
                        "retweet_count": 12,
                        "reply_count": 15,
                        "quote_count": 3,
                        "view_count": 12000
                    },
                    {
                        "tweet_id": "promo-1",
                        "account_handle": "mx",
                        "author_handle": "mx",
                        "kind": "post",
                        "created_at": (now - timedelta(minutes=3)).isoformat(),
                        "text": "promo launch link in bio",
                        "conversation_id": "conv-promo",
                        "favorite_count": 10,
                        "retweet_count": 1,
                        "reply_count": 0,
                        "quote_count": 0,
                        "view_count": 100
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    taxonomy_file.write_text(json.dumps(DEFAULT_TAXONOMY_DOC), encoding="utf-8")
    state_file.write_text(
        json.dumps(
            {
                "last_run_at": (now - timedelta(minutes=20)).isoformat(),
                "threads": {
                    "conv-heated": {
                        "title": "Tracked heated thread",
                        "heat_status": "heated",
                        "momentum": "steady",
                        "virality_score": 4.0,
                        "disagreement_present": True,
                        "last_seen_at": (now - timedelta(hours=1)).isoformat(),
                        "source_urls": ["https://x.com/mx/status/heated-1"]
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = run_digest_report(
        timeline_file=timeline_file,
        output_dir=output_dir,
        state_file=state_file,
        taxonomy_file=taxonomy_file,
        backend=_FakeBackend(),
    )

    assert result.selected_count == 4
    assert result.kept_count == 2
    assert result.issue_count == 1
    assert result.digest_path.exists()

    digest_text = result.digest_path.read_text(encoding="utf-8")
    assert "## Top Issues" in digest_text
    assert "## Heated Threads Watch" in digest_text
    assert "## Standout Signals" in digest_text
    assert "https://x.com/mx/status/fresh-1" in digest_text

    run_dir = result.run_dir
    for filename in (
        "selected_entries.json",
        "candidates.json",
        "assembled_units.json",
        "categorized_units.json",
        "filtered_units.json",
        "signals.json",
        "issues.json",
        "run.json",
    ):
        assert (run_dir / filename).exists()

    state_doc = json.loads(state_file.read_text(encoding="utf-8"))
    assert state_doc["last_run_at"]
    assert "conv-fresh" in state_doc["threads"]
    assert state_doc["threads"]["conv-fresh"]["heat_status"] in {"heated", "still_active"}

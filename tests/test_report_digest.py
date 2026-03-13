from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from xs2n.agents.digest import (
    CategorizationResult,
    DEFAULT_TAXONOMY_DOC,
    FilterResult,
    IssueAssignmentResult,
    ThreadProcessResult,
    TimelineRecord,
    _load_threads,
    _virality_score,
    run_digest_report,
)


class _FakeLLM:
    def __init__(self, *, fail_schema=None) -> None:  # noqa: ANN001
        self._fail_schema = fail_schema
        self._trace_dir: Path | None = None
        self._call_index = 0

    def configure_run_logging(self, *, run_dir: Path) -> None:
        self._trace_dir = run_dir / "llm_calls"
        self._trace_dir.mkdir(parents=True, exist_ok=True)
        self._call_index = 0

    def _phase_name(self, schema) -> str:  # noqa: ANN001, ANN201
        if schema is CategorizationResult:
            return "categorize_threads"
        if schema is FilterResult:
            return "filter_threads"
        if schema is ThreadProcessResult:
            return "process_threads"
        if schema is IssueAssignmentResult:
            return "group_issues"
        return "llm"

    def _item_id(self, payload) -> str | None:  # noqa: ANN001, ANN201
        thread = payload.get("thread") if isinstance(payload, dict) else payload
        return getattr(thread, "thread_id", None)

    def _write_trace(
        self,
        *,
        prompt: str,
        payload,
        schema,
        result=None,
        error: str | None = None,
    ) -> None:  # noqa: ANN001, ANN201
        if self._trace_dir is None:
            return
        self._call_index += 1
        if hasattr(payload, "model_dump"):
            payload_doc = payload.model_dump(mode="json")
        elif isinstance(payload, dict):
            payload_doc = {
                key: value.model_dump(mode="json") if hasattr(value, "model_dump") else value
                for key, value in payload.items()
            }
        else:
            payload_doc = payload
        trace = {
            "call_id": self._call_index,
            "phase": self._phase_name(schema),
            "item_id": self._item_id(payload),
            "schema_name": schema.__name__,
            "prompt": prompt,
            "payload": payload_doc,
            "result": result.model_dump(mode="json") if result is not None else None,
            "error_message": error,
        }
        item_suffix = re.sub(
            r"[^a-zA-Z0-9_.-]+",
            "_",
            trace["item_id"] or f"call_{self._call_index:03d}",
        ).strip("_")
        path = self._trace_dir / (
            f"{self._call_index:03d}_{trace['phase']}_{item_suffix}.json"
        )
        path.write_text(f"{json.dumps(trace, indent=2)}\n", encoding="utf-8")

    def run(self, *, prompt, payload, schema):  # noqa: ANN001, ANN201
        if schema is self._fail_schema:
            self._write_trace(
                prompt=prompt,
                payload=payload,
                schema=schema,
                error="synthetic failure",
            )
            raise RuntimeError("synthetic failure")

        if schema is CategorizationResult:
            thread = payload["thread"]
            joined_text = " ".join(tweet.text.lower() for tweet in thread.tweets)
            if "promo" in joined_text:
                category = "promo"
            elif "debate" in joined_text:
                category = "debate"
            else:
                category = "analysis"
            result = CategorizationResult(
                category=category,
                subcategory=None,
                editorial_angle="scaffold",
                reasoning="Deterministic test categorization.",
            )
            self._write_trace(prompt=prompt, payload=payload, schema=schema, result=result)
            return result

        if schema is FilterResult:
            thread = payload["thread"]
            result = FilterResult(
                keep=thread.category != "promo",
                filter_reason="keep_for_signal" if thread.category != "promo" else "drop_promo",
            )
            self._write_trace(prompt=prompt, payload=payload, schema=schema, result=result)
            return result

        if schema is ThreadProcessResult:
            thread = payload
            joined_text = " ".join(tweet.text.lower() for tweet in thread.tweets)
            disagreement = "debate" in joined_text
            result = ThreadProcessResult(
                headline=thread.tweets[0].text[:40],
                main_claim=thread.tweets[0].text,
                why_it_matters="This matters for the digest.",
                key_entities=[thread.account_handle],
                disagreement_present=disagreement,
                disagreement_summary="There is visible pushback." if disagreement else None,
                novelty_label="fresh",
                signal_score=82 if disagreement else 70,
            )
            self._write_trace(prompt=prompt, payload=payload, schema=schema, result=result)
            return result

        if schema is IssueAssignmentResult:
            thread = payload
            result = IssueAssignmentResult(
                issue_slug="main_topic",
                issue_title="Main Topic",
                issue_summary="Grouped issue summary.",
                why_this_thread_belongs=f"{thread.headline} belongs here.",
            )
            self._write_trace(prompt=prompt, payload=payload, schema=schema, result=result)
            return result

        raise AssertionError(f"Unexpected schema: {schema}")


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


def test_load_threads_groups_source_authored_conversations(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    timeline_file = tmp_path / "timeline.json"
    timeline_file.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "tweet_id": "source-1",
                        "account_handle": "mx",
                        "author_handle": "mx",
                        "kind": "post",
                        "created_at": (now - timedelta(minutes=3)).isoformat(),
                        "text": "thread root",
                        "conversation_id": "conv-1",
                    },
                    {
                        "tweet_id": "source-2",
                        "account_handle": "mx",
                        "author_handle": "mx",
                        "kind": "reply",
                        "created_at": (now - timedelta(minutes=2)).isoformat(),
                        "text": "thread continuation",
                        "conversation_id": "conv-1",
                    },
                    {
                        "tweet_id": "reply-1",
                        "account_handle": "mx",
                        "author_handle": "other",
                        "kind": "reply",
                        "created_at": (now - timedelta(minutes=1)).isoformat(),
                        "text": "outside reply",
                        "conversation_id": "conv-1",
                    },
                    {
                        "tweet_id": "outside-only",
                        "account_handle": "mx",
                        "author_handle": "other",
                        "kind": "reply",
                        "created_at": now.isoformat(),
                        "text": "ignore this conversation",
                        "conversation_id": "conv-2",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    threads = _load_threads(timeline_file=timeline_file)

    assert len(threads) == 1
    assert threads[0].thread_id == "conv-1"
    assert threads[0].source_tweet_ids == ["source-1", "source-2"]
    assert threads[0].context_tweet_ids == ["reply-1"]


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


def test_run_digest_report_writes_artifacts_and_markdown(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    timeline_file = tmp_path / "timeline.json"
    taxonomy_file = tmp_path / "taxonomy.json"
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
                        "view_count": 5000,
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
                        "view_count": 9000,
                    },
                    {
                        "tweet_id": "promo-1",
                        "account_handle": "mx",
                        "author_handle": "mx",
                        "kind": "post",
                        "created_at": (now - timedelta(minutes=3)).isoformat(),
                        "text": "promo post buy now",
                        "conversation_id": "conv-promo",
                        "favorite_count": 5,
                        "retweet_count": 1,
                        "reply_count": 0,
                        "quote_count": 0,
                        "view_count": 200,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    taxonomy_file.write_text(
        json.dumps(DEFAULT_TAXONOMY_DOC),
        encoding="utf-8",
    )

    result = run_digest_report(
        timeline_file=timeline_file,
        output_dir=output_dir,
        taxonomy_file=taxonomy_file,
        model="fake-model",
        llm=_FakeLLM(),
    )

    expected_files = {
        "threads.json",
        "categorized_threads.json",
        "filtered_threads.json",
        "processed_threads.json",
        "issue_assignments.json",
        "issues.json",
        "taxonomy.json",
        "phases.json",
        "llm_calls",
        "run.json",
        "digest.md",
    }
    produced_files = {path.name for path in result.run_dir.iterdir()}

    assert expected_files.issubset(produced_files)
    assert result.thread_count == 2
    assert result.kept_count == 1
    assert result.issue_count == 1

    digest_text = result.digest_path.read_text(encoding="utf-8")
    assert "## Top Issues" in digest_text
    assert "## Standout Threads" in digest_text
    assert "https://x.com/mx/status/fresh-1" in digest_text

    run_doc = json.loads((result.run_dir / "run.json").read_text(encoding="utf-8"))
    phases_doc = json.loads((result.run_dir / "phases.json").read_text(encoding="utf-8"))
    taxonomy_snapshot = json.loads(
        (result.run_dir / "taxonomy.json").read_text(encoding="utf-8")
    )
    llm_call_paths = sorted((result.run_dir / "llm_calls").iterdir())

    assert run_doc["status"] == "completed"
    assert run_doc["thread_count"] == 2
    assert run_doc["kept_count"] == 1
    assert run_doc["issue_count"] == 1
    assert run_doc["phase_counts"]["categorized_threads"] == 2
    assert run_doc["phase_counts"]["issues"] == 1
    assert run_doc["taxonomy_snapshot_path"].endswith("taxonomy.json")
    assert run_doc["llm_calls_dir"].endswith("llm_calls")
    assert [phase["name"] for phase in phases_doc] == [
        "load_taxonomy",
        "load_threads",
        "categorize_threads",
        "filter_threads",
        "process_threads",
        "group_issues",
        "render_digest",
    ]
    assert all(phase["status"] == "completed" for phase in phases_doc)
    assert taxonomy_snapshot == DEFAULT_TAXONOMY_DOC
    assert len(llm_call_paths) == 6

    categorize_call_docs = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in llm_call_paths
        if "categorize_threads" in path.name
    ]
    assert len(categorize_call_docs) == 2
    assert all(doc["schema_name"] == "CategorizationResult" for doc in categorize_call_docs)
    assert {doc["result"]["category"] for doc in categorize_call_docs} == {"debate", "promo"}


def test_run_digest_report_records_failed_phase_artifacts(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    timeline_file = tmp_path / "timeline.json"
    taxonomy_file = tmp_path / "taxonomy.json"
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
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    taxonomy_file.write_text(
        json.dumps(DEFAULT_TAXONOMY_DOC),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="synthetic failure"):
        run_digest_report(
            timeline_file=timeline_file,
            output_dir=output_dir,
            taxonomy_file=taxonomy_file,
            model="fake-model",
            llm=_FakeLLM(fail_schema=ThreadProcessResult),
        )

    run_dir = next(output_dir.iterdir())
    run_doc = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    phases_doc = json.loads((run_dir / "phases.json").read_text(encoding="utf-8"))
    llm_call_paths = sorted((run_dir / "llm_calls").iterdir())

    assert run_doc["status"] == "failed"
    assert run_doc["failed_phase"] == "process_threads"
    assert run_doc["error_message"] == "synthetic failure"
    assert phases_doc[-1]["name"] == "process_threads"
    assert phases_doc[-1]["status"] == "failed"
    assert phases_doc[-1]["error_message"] == "synthetic failure"
    assert not (run_dir / "digest.md").exists()
    assert any("process_threads" in path.name for path in llm_call_paths)

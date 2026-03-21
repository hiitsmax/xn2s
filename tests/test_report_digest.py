from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading

import pytest

from xs2n.agents.digest import render_issue_digest_html, run_issue_report
from xs2n.agents.digest.helpers import virality_score
from xs2n.agents.digest.steps.load_threads import run as load_threads
from xs2n.schemas.digest import TimelineRecord
from xs2n.schemas.run_events import RunEvent


class _FakeLLM:
    def __init__(
        self,
        *,
        fail_schema_name: str | None = None,
    ) -> None:
        self._fail_schema_name = fail_schema_name
        self._trace_dir: Path | None = None
        self._call_index = 0
        self._trace_lock = threading.Lock()
        self.image_urls_by_schema_name: dict[str, list[list[str]]] = {}

    def configure_run_logging(self, *, run_dir: Path) -> None:
        self._trace_dir = run_dir / "llm_calls"
        self._trace_dir.mkdir(parents=True, exist_ok=True)
        with self._trace_lock:
            self._call_index = 0

    def _phase_name(self, schema_name: str) -> str:
        if schema_name == "ThreadFilterResult":
            return "filter_threads"
        if schema_name in {"IssueSelectionResult", "IssueWriteResult"}:
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
        schema_name: str,
        result=None,
        error: str | None = None,
        image_urls: list[str] | None = None,
        phase_name: str | None = None,
        item_id: str | None = None,
    ) -> None:  # noqa: ANN001, ANN201
        if self._trace_dir is None:
            return
        with self._trace_lock:
            self._call_index += 1
            call_id = self._call_index
        payload_doc = self._to_jsonable(payload)
        trace = {
            "call_id": call_id,
            "phase": phase_name or self._phase_name(schema_name),
            "item_id": item_id or self._item_id(payload),
            "schema_name": schema_name,
            "prompt": prompt,
            "payload": payload_doc,
            "image_urls": image_urls or [],
            "result": result,
            "error_message": error,
        }
        item_suffix = re.sub(
            r"[^a-zA-Z0-9_.-]+",
            "_",
            trace["item_id"] or f"call_{call_id:03d}",
        ).strip("_")
        path = self._trace_dir / (
            f"{call_id:03d}_{trace['phase']}_{item_suffix}.json"
        )
        path.write_text(f"{json.dumps(trace, indent=2)}\n", encoding="utf-8")

    def _to_jsonable(self, value):  # noqa: ANN001, ANN201
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {
                key: self._to_jsonable(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._to_jsonable(item) for item in value]
        return value

    def run(
        self,
        *,
        prompt,
        payload,
        schema,
        image_urls=None,
        phase_name: str | None = None,
        item_id: str | None = None,
    ):  # noqa: ANN001, ANN201
        schema_name = schema.__name__
        image_urls = image_urls or []
        self.image_urls_by_schema_name.setdefault(schema_name, []).append(image_urls)

        if schema_name == self._fail_schema_name:
            self._write_trace(
                prompt=prompt,
                payload=payload,
                schema_name=schema_name,
                error="synthetic failure",
                image_urls=image_urls,
                phase_name=phase_name,
                item_id=item_id,
            )
            raise RuntimeError("synthetic failure")

        if schema_name == "ThreadFilterResult":
            thread = payload["thread"]
            joined_text = " ".join(tweet.text.lower() for tweet in thread.tweets)
            result = {
                "keep": "buy now" not in joined_text and "gm gm gm" not in joined_text,
                "filter_reason": (
                    "drop_obvious_noise"
                    if "buy now" in joined_text or "gm gm gm" in joined_text
                    else "keep_real_signal"
                ),
            }
            self._write_trace(
                prompt=prompt,
                payload=payload,
                schema_name=schema_name,
                result=result,
                image_urls=image_urls,
                phase_name=phase_name,
                item_id=item_id,
            )
            return schema.model_validate(result)

        if schema_name == "IssueSelectionResult":
            thread = payload["thread"]
            issue_candidates = payload["issues"]
            if issue_candidates:
                result = {
                    "action": "update_existing_issue",
                    "issue_slug": issue_candidates[0]["slug"],
                    "reasoning": "Same running story.",
                }
            else:
                result = {
                    "action": "create_new_issue",
                    "issue_slug": "chip_race",
                    "reasoning": "First thread creates the issue.",
                }
            self._write_trace(
                prompt=prompt,
                payload=payload,
                schema_name=schema_name,
                result=result,
                image_urls=image_urls,
                phase_name=phase_name,
                item_id=item_id,
            )
            return schema.model_validate(result)

        if schema_name == "IssueWriteResult":
            thread = payload["thread"]
            selection = payload["selection"]
            issue_slug = selection.issue_slug or "chip_race"
            resolved_thread = thread.get("thread") if isinstance(thread, dict) else thread
            primary_tweet = (
                resolved_thread.primary_tweet
                if hasattr(resolved_thread, "primary_tweet")
                else resolved_thread["primary_tweet"]
            )
            result = {
                "issue_slug": issue_slug,
                "issue_title": "Chip Race",
                "issue_summary": "Why AI chip supply keeps driving the conversation.",
                "thread_title": f"Thread about {primary_tweet['text'][:24] if isinstance(primary_tweet, dict) else primary_tweet.text[:24]}",
                "thread_summary": (
                    primary_tweet["text"]
                    if isinstance(primary_tweet, dict)
                    else primary_tweet.text
                ),
                "why_this_thread_belongs": "It adds a concrete development to the same issue.",
            }
            self._write_trace(
                prompt=prompt,
                payload=payload,
                schema_name=schema_name,
                result=result,
                image_urls=image_urls,
                phase_name=phase_name,
                item_id=item_id,
            )
            return schema.model_validate(result)

        raise AssertionError(f"Unexpected schema: {schema_name}")


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
    media: list[dict[str, object]] | None = None,
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
            "media": media or [],
        }
    )


def test_load_threads_groups_source_authored_conversations_and_exposes_primary_post(
    tmp_path: Path,
) -> None:
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
                        "media": [
                            {
                                "media_url": "https://img.test/root.png",
                                "media_type": "photo",
                                "width": 1200,
                                "height": 800,
                            }
                        ],
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
                        "media": [
                            {
                                "media_url": "https://img.test/reply.png",
                                "media_type": "photo",
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    threads = load_threads(timeline_file=timeline_file)

    assert len(threads) == 1
    assert threads[0].thread_id == "conv-1"
    assert threads[0].source_tweet_ids == ["source-1", "source-2"]
    assert threads[0].context_tweet_ids == ["reply-1"]
    assert threads[0].primary_tweet.tweet_id == "source-1"
    assert threads[0].primary_tweet_media_urls == ["https://img.test/root.png"]


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

    assert virality_score(high) > virality_score(low)


def test_agents_package_exports_only_active_report_entrypoints() -> None:
    import xs2n.agents as agents_module
    import xs2n.agents.digest as digest_module

    assert not hasattr(agents_module, "run_digest_report")
    assert "run_digest_report" not in digest_module.__all__
    assert not hasattr(digest_module, "run_digest_report")


def test_run_issue_report_writes_artifacts_and_issue_json(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    timeline_file = tmp_path / "timeline.json"
    output_dir = tmp_path / "report_runs"

    timeline_file.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "tweet_id": "chip-1",
                        "account_handle": "mx",
                        "author_handle": "mx",
                        "kind": "post",
                        "created_at": (now - timedelta(minutes=5)).isoformat(),
                        "text": "Nvidia supply is tightening again",
                        "conversation_id": "conv-chip-1",
                        "favorite_count": 50,
                        "retweet_count": 8,
                        "reply_count": 6,
                        "quote_count": 2,
                        "view_count": 5000,
                        "media": [
                            {
                                "media_url": "https://img.test/chip-1.png",
                                "media_type": "photo",
                            }
                        ],
                    },
                    {
                        "tweet_id": "chip-2",
                        "account_handle": "mx",
                        "author_handle": "mx",
                        "kind": "post",
                        "created_at": (now - timedelta(minutes=3)).isoformat(),
                        "text": "TSMC capacity is still the bottleneck",
                        "conversation_id": "conv-chip-2",
                        "favorite_count": 30,
                        "retweet_count": 5,
                        "reply_count": 4,
                        "quote_count": 1,
                        "view_count": 3000,
                    },
                    {
                        "tweet_id": "noise-1",
                        "account_handle": "mx",
                        "author_handle": "mx",
                        "kind": "post",
                        "created_at": (now - timedelta(minutes=1)).isoformat(),
                        "text": "gm gm gm buy now",
                        "conversation_id": "conv-noise",
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

    result = run_issue_report(
        timeline_file=timeline_file,
        output_dir=output_dir,
        model="fake-model",
        llm=_FakeLLM(),
    )

    expected_files = {
        "threads.json",
        "filtered_threads.json",
        "issue_assignments.json",
        "issues.json",
        "phases.json",
        "llm_calls",
        "run.json",
    }
    produced_files = {path.name for path in result.run_dir.iterdir()}

    assert expected_files.issubset(produced_files)
    assert result.thread_count == 3
    assert result.kept_count == 2
    assert result.issue_count == 1

    issues_doc = json.loads((result.run_dir / "issues.json").read_text(encoding="utf-8"))
    assignments_doc = json.loads(
        (result.run_dir / "issue_assignments.json").read_text(encoding="utf-8")
    )
    run_doc = json.loads((result.run_dir / "run.json").read_text(encoding="utf-8"))
    phases_doc = json.loads((result.run_dir / "phases.json").read_text(encoding="utf-8"))
    llm_call_paths = sorted((result.run_dir / "llm_calls").iterdir())

    assert [issue["slug"] for issue in issues_doc] == ["chip_race"]
    assert len(assignments_doc) == 2
    assert {assignment["thread_id"] for assignment in assignments_doc} == {
        "conv-chip-1",
        "conv-chip-2",
    }
    assert run_doc["status"] == "completed"
    assert run_doc["thread_count"] == 3
    assert run_doc["kept_count"] == 2
    assert run_doc["issue_count"] == 1
    assert run_doc["digest_title"] == "Chip Race"
    assert run_doc["primary_artifact_path"] is None
    assert [phase["name"] for phase in phases_doc] == [
        "load_threads",
        "filter_threads",
        "group_issues",
    ]
    assert all(phase["status"] == "completed" for phase in phases_doc)
    assert len(llm_call_paths) == 7


def test_run_issue_report_uses_only_primary_post_images_in_llm_calls(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    timeline_file = tmp_path / "timeline.json"
    output_dir = tmp_path / "report_runs"
    fake_llm = _FakeLLM()

    timeline_file.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "tweet_id": "root-1",
                        "account_handle": "mx",
                        "author_handle": "mx",
                        "kind": "post",
                        "created_at": (now - timedelta(minutes=5)).isoformat(),
                        "text": "Interesting chart about foundry constraints",
                        "conversation_id": "conv-1",
                        "media": [
                            {
                                "media_url": "https://img.test/root.png",
                                "media_type": "photo",
                            }
                        ],
                    },
                    {
                        "tweet_id": "reply-1",
                        "account_handle": "mx",
                        "author_handle": "other",
                        "kind": "reply",
                        "created_at": (now - timedelta(minutes=4)).isoformat(),
                        "text": "reply with image",
                        "conversation_id": "conv-1",
                        "media": [
                            {
                                "media_url": "https://img.test/reply.png",
                                "media_type": "photo",
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    run_issue_report(
        timeline_file=timeline_file,
        output_dir=output_dir,
        model="fake-model",
        llm=fake_llm,
    )

    assert fake_llm.image_urls_by_schema_name["ThreadFilterResult"] == [
        ["https://img.test/root.png"]
    ]
    assert fake_llm.image_urls_by_schema_name["IssueSelectionResult"] == [
        ["https://img.test/root.png"]
    ]
    assert fake_llm.image_urls_by_schema_name["IssueWriteResult"] == [
        ["https://img.test/root.png"]
    ]


def test_run_issue_report_emits_run_and_phase_events(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    timeline_file = tmp_path / "timeline.json"
    output_dir = tmp_path / "report_runs"
    events: list[RunEvent] = []

    timeline_file.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "tweet_id": "chip-1",
                        "account_handle": "mx",
                        "author_handle": "mx",
                        "kind": "post",
                        "created_at": now.isoformat(),
                        "text": "Foundry supply is tightening.",
                        "conversation_id": "conv-chip-1",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = run_issue_report(
        timeline_file=timeline_file,
        output_dir=output_dir,
        model="fake-model",
        llm=_FakeLLM(),
        emit_event=events.append,
    )

    assert events[0].event == "run_started"
    assert events[0].run_id == result.run_id
    assert any(
        event.event == "phase_started" and event.phase == "load_threads"
        for event in events
    )
    assert any(
        event.event == "artifact_written"
        and event.artifact_path is not None
        and event.artifact_path.endswith("threads.json")
        for event in events
    )
    assert any(
        event.event == "phase_completed" and event.phase == "group_issues"
        for event in events
    )
    assert events[-1].event == "run_completed"
    assert events[-1].counts == {
        "thread_count": 1,
        "kept_count": 1,
        "issue_count": 1,
    }


def test_render_issue_digest_html_uses_saved_issue_artifacts_only(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    timeline_file = tmp_path / "timeline.json"
    output_dir = tmp_path / "report_runs"

    timeline_file.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "tweet_id": "chip-1",
                        "account_handle": "mx",
                        "author_handle": "mx",
                        "kind": "post",
                        "created_at": now.isoformat(),
                        "text": "Foundry supply is tightening.",
                        "conversation_id": "conv-chip-1",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = run_issue_report(
        timeline_file=timeline_file,
        output_dir=output_dir,
        model="fake-model",
        llm=_FakeLLM(),
    )
    (result.run_dir / "threads.json").unlink()
    (result.run_dir / "filtered_threads.json").unlink()

    html_path = render_issue_digest_html(run_dir=result.run_dir)

    html_text = html_path.read_text(encoding="utf-8")
    run_doc = json.loads((result.run_dir / "run.json").read_text(encoding="utf-8"))

    assert html_path.name == "digest.html"
    assert "<html" in html_text.lower()
    assert "Chip Race" in html_text
    assert "Why AI chip supply keeps driving the conversation." in html_text
    assert run_doc["primary_artifact_path"].endswith("digest.html")
    assert run_doc["digest_title"] == "Chip Race"


def test_run_issue_report_records_failed_phase_artifacts(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    timeline_file = tmp_path / "timeline.json"
    output_dir = tmp_path / "report_runs"

    timeline_file.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "tweet_id": "chip-1",
                        "account_handle": "mx",
                        "author_handle": "mx",
                        "kind": "post",
                        "created_at": now.isoformat(),
                        "text": "One real thread",
                        "conversation_id": "conv-chip-1",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="synthetic failure"):
        run_issue_report(
            timeline_file=timeline_file,
            output_dir=output_dir,
            model="fake-model",
            llm=_FakeLLM(fail_schema_name="IssueWriteResult"),
        )

    run_dir = next(output_dir.iterdir())
    run_doc = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    phases_doc = json.loads((run_dir / "phases.json").read_text(encoding="utf-8"))
    llm_call_paths = sorted((run_dir / "llm_calls").iterdir())

    assert run_doc["status"] == "failed"
    assert run_doc["failed_phase"] == "group_issues"
    assert run_doc["error_message"] == "synthetic failure"
    assert phases_doc[-1]["name"] == "group_issues"
    assert phases_doc[-1]["status"] == "failed"
    assert phases_doc[-1]["error_message"] == "synthetic failure"
    assert not (run_dir / "digest.html").exists()
    assert any("group_issues" in path.name for path in llm_call_paths)

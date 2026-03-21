from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from xs2n.report_runtime import (
    IssuesRunArguments,
    LatestRunArguments,
    run_latest_report,
)
from xs2n.schemas.run_events import RunEvent


def test_issues_run_arguments_match_report_issues_cli_contract() -> None:
    arguments = IssuesRunArguments.from_form(
        timeline_file="",
        output_dir="",
        model="",
    )

    assert arguments.to_cli_args() == [
        "report",
        "issues",
        "--timeline-file",
        "data/timeline.json",
        "--output-dir",
        "data/report_runs",
        "--model",
        "gpt-5.4-mini",
    ]
    assert arguments.to_command().label == "report issues"


def test_latest_run_arguments_drop_dead_storage_fields() -> None:
    arguments = LatestRunArguments.from_form(
        since="2026-03-18T00:00:00Z",
        lookback_hours="24",
        cookies_file="cookies.json",
        limit="100",
        timeline_file="data/timeline.json",
        sources_file="data/sources.json",
        home_latest=False,
        output_dir="data/report_runs",
        taxonomy_file="docs/codex/report_taxonomy.json",
        model="gpt-5.4-mini",
        parallel_workers="3",
    )

    assert arguments.to_storage_doc() == {
        "since": "2026-03-18T00:00:00Z",
        "lookback_hours": 24,
        "cookies_file": "cookies.json",
        "limit": 100,
        "timeline_file": "data/timeline.json",
        "sources_file": "data/sources.json",
        "home_latest": False,
        "output_dir": "data/report_runs",
        "model": "gpt-5.4-mini",
    }
    assert "--taxonomy-file" not in arguments.to_cli_args()
    assert "--parallel-workers" not in arguments.to_cli_args()


def test_run_latest_report_runs_timeline_then_windowed_issues_then_render(
    monkeypatch,
    tmp_path: Path,
) -> None:
    timeline_calls: list[dict[str, object]] = []
    issue_calls: list[dict[str, object]] = []
    render_calls: list[dict[str, object]] = []
    messages: list[str] = []

    monkeypatch.setattr(
        "xs2n.report_runtime.run_timeline_ingestion",
        lambda **kwargs: timeline_calls.append(kwargs)
        or kwargs["timeline_file"].write_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "tweet_id": "old-1",
                            "account_handle": "mx",
                            "author_handle": "mx",
                            "kind": "post",
                            "created_at": "2026-03-17T23:59:00+00:00",
                            "text": "old",
                            "conversation_id": "conv-old",
                        },
                        {
                            "tweet_id": "fresh-1",
                            "account_handle": "mx",
                            "author_handle": "mx",
                            "kind": "post",
                            "created_at": "2026-03-18T01:00:00+00:00",
                            "text": "fresh",
                            "conversation_id": "conv-fresh",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        ),
    )
    arguments = LatestRunArguments(
        since="2026-03-18T00:00:00Z",
        lookback_hours=24,
        cookies_file=tmp_path / "cookies.json",
        limit=200,
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        home_latest=True,
        output_dir=tmp_path / "report_runs",
        model="gpt-5.4",
    )

    result = run_latest_report(
        arguments,
        now=datetime(2026, 3, 18, 19, 0, tzinfo=timezone.utc),
        echo=messages.append,
        run_issue_report_fn=lambda **kwargs: issue_calls.append(kwargs)
        or SimpleNamespace(
            run_id="20260318T190000Z",
            run_dir=tmp_path / "report_runs" / "20260318T190000Z",
            thread_count=6,
            kept_count=4,
            issue_count=2,
        ),
        render_issue_digest_html_fn=lambda **kwargs: render_calls.append(kwargs)
        or tmp_path / "report_runs" / "20260318T190000Z" / "digest.html",
    )

    assert result.run_id == "20260318T190000Z"
    assert result.digest_path == tmp_path / "report_runs" / "20260318T190000Z" / "digest.html"
    assert timeline_calls == [
        {
            "account": None,
            "from_sources": False,
            "home_latest": True,
            "since": "2026-03-18T00:00:00+00:00",
            "cookies_file": tmp_path / "cookies.json",
            "limit": 200,
            "timeline_file": tmp_path / "timeline.json",
            "sources_file": tmp_path / "sources.json",
        }
    ]
    assert len(issue_calls) == 1
    assert issue_calls[0]["output_dir"] == tmp_path / "report_runs"
    assert issue_calls[0]["model"] == "gpt-5.4"
    snapshot_doc = json.loads(
        issue_calls[0]["timeline_file"].read_text(encoding="utf-8")
    )
    assert snapshot_doc == {
        "entries": [
            {
                "tweet_id": "fresh-1",
                "account_handle": "mx",
                "author_handle": "mx",
                "kind": "post",
                "created_at": "2026-03-18T01:00:00+00:00",
                "text": "fresh",
                "conversation_id": "conv-fresh",
            }
        ]
    }
    assert render_calls == [
        {"run_dir": tmp_path / "report_runs" / "20260318T190000Z"}
    ]
    assert messages == [
        "Ingesting Home->Following latest timeline before issue generation (since 2026-03-18T00:00:00+00:00).",
        "Latest issue run 20260318T190000Z: loaded 6 threads, kept 4 threads, produced 2 issues.",
        f"Rendered HTML digest to {tmp_path / 'report_runs' / '20260318T190000Z' / 'digest.html'}.",
    ]


def test_run_latest_report_emits_progress_events(
    monkeypatch,
    tmp_path: Path,
) -> None:
    events: list[RunEvent] = []

    monkeypatch.setattr(
        "xs2n.report_runtime.run_timeline_ingestion",
        lambda **kwargs: kwargs["timeline_file"].write_text(
            '{"entries": []}\n',
            encoding="utf-8",
        ),
    )

    arguments = LatestRunArguments(
        since="2026-03-18T00:00:00Z",
        cookies_file=tmp_path / "cookies.json",
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        output_dir=tmp_path / "report_runs",
        model="gpt-5.4-mini",
    )

    def fake_run_issue_report(**kwargs):
        kwargs["emit_event"](
            RunEvent(
                event="run_started",
                message="Issue run 20260318T190000Z started.",
                run_id="20260318T190000Z",
            )
        )
        kwargs["emit_event"](
            RunEvent(
                event="run_completed",
                message="Issue run 20260318T190000Z completed.",
                run_id="20260318T190000Z",
                counts={"thread_count": 0, "kept_count": 0, "issue_count": 0},
            )
        )
        return SimpleNamespace(
            run_id="20260318T190000Z",
            run_dir=tmp_path / "report_runs" / "20260318T190000Z",
            thread_count=0,
            kept_count=0,
            issue_count=0,
        )

    def fake_render_issue_digest_html(**kwargs):
        digest_path = tmp_path / "report_runs" / "20260318T190000Z" / "digest.html"
        kwargs["emit_event"](
            RunEvent(
                event="artifact_written",
                message="Rendered HTML digest artifact.",
                run_id="20260318T190000Z",
                phase="render_digest_html",
                artifact_path=str(digest_path),
            )
        )
        return digest_path

    run_latest_report(
        arguments,
        emit_event=events.append,
        echo=lambda _message: None,
        run_issue_report_fn=fake_run_issue_report,
        render_issue_digest_html_fn=fake_render_issue_digest_html,
    )

    assert [(event.event, event.phase, event.run_id) for event in events] == [
        ("phase_started", "timeline_ingestion", None),
        ("phase_completed", "timeline_ingestion", None),
        ("artifact_written", "timeline_window", None),
        ("run_started", None, "20260318T190000Z"),
        ("run_completed", None, "20260318T190000Z"),
        ("artifact_written", "render_digest_html", "20260318T190000Z"),
    ]

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from xs2n.report_runtime import LatestRunArguments, run_latest_report


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
        taxonomy_file=tmp_path / "taxonomy.json",
        model="gpt-5.4",
        parallel_workers=5,
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

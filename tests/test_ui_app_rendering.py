from __future__ import annotations

import json
from queue import Queue
from types import SimpleNamespace

import pytest

import xs2n.ui.app as app
from xs2n.ui.artifacts import ArtifactRecord, ArtifactSectionRecord


class FakeBrowser:
    def __init__(self) -> None:
        self.selection = 0

    def value(self, selection: int | None = None) -> int:
        if selection is None:
            return self.selection
        self.selection = selection
        return self.selection


class FakeViewer:
    def __init__(self) -> None:
        self.html = ""
        self.top = None
        self.left = None

    def value(self, html: str) -> None:
        self.html = html

    def topline(self, line: int) -> None:
        self.top = line

    def leftline(self, line: int) -> None:
        self.left = line


class FakeStatus:
    def __init__(self) -> None:
        self.text = ""

    def value(self, text: str) -> None:
        self.text = text


def _write_json(path: app.Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _issue_thread_payload() -> dict[str, object]:
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
    return {
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


def test_apply_selected_artifact_name_schedules_preview_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    browser.artifacts = [
        ArtifactRecord(
            name="digest.md",
            path=app.Path("digest.md"),
            kind="markdown",
            exists=True,
        ),
        ArtifactRecord(
            name="run.json",
            path=app.Path("run.json"),
            kind="json",
            exists=True,
        ),
        ArtifactRecord(
            name="llm_calls/001_trace.json",
            path=app.Path("llm_calls/001_trace.json"),
            kind="json",
            exists=True,
        ),
    ]
    browser.sections = [
        ArtifactSectionRecord(
            icon="◆",
            label="Digest",
            artifact_name="digest.md",
        ),
        ArtifactSectionRecord(
            icon="▣",
            label="Run metadata",
            artifact_name="run.json",
        ),
    ]
    browser.sections_browser = FakeBrowser()
    browser.raw_files_browser = FakeBrowser()
    browser.viewer = FakeViewer()
    browser.status_output = FakeStatus()
    browser.viewer_render_results = Queue()
    browser.selected_artifact_name = None
    browser.pending_viewer_artifact_name = None
    browser.rendered_viewer_artifact_name = None
    browser.pending_viewer_request_id = 0
    scheduled_artifacts: list[str] = []

    browser._schedule_artifact_preview_render = lambda artifact: (
        scheduled_artifacts.append(artifact.name),
        setattr(
            browser,
            "pending_viewer_request_id",
            browser.pending_viewer_request_id + 1,
        ),
    )
    monkeypatch.setattr(
        app,
        "render_loading_artifact_html",
        lambda artifact: f"<loading>{artifact.name}</loading>",
    )

    app.ArtifactBrowserWindow._apply_selected_artifact_name(browser, "run.json")

    assert browser.selected_artifact_name == "run.json"
    assert browser.sections_browser.selection == 2
    assert browser.raw_files_browser.selection == 2
    assert browser.pending_viewer_artifact_name == "run.json"
    assert browser.rendered_viewer_artifact_name is None
    assert browser.viewer.html == "<loading>run.json</loading>"
    assert browser.viewer.top == 0
    assert browser.viewer.left == 0
    assert browser.status_output.text == "Loading run.json..."
    assert scheduled_artifacts == ["run.json"]


def test_drain_pending_viewer_render_uses_latest_completed_result() -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    browser.viewer = FakeViewer()
    browser.status_output = FakeStatus()
    browser.viewer_render_results = Queue()
    browser.selected_artifact_name = "run.json"
    browser.pending_viewer_artifact_name = "run.json"
    browser.rendered_viewer_artifact_name = None
    browser.pending_viewer_request_id = 2
    browser.viewer_render_results.put(
        app.ViewerRenderResult(
            request_id=1,
            artifact_name="digest.md",
            html="<html>digest.md</html>",
            status_text="Viewing digest.md.",
        )
    )
    browser.viewer_render_results.put(
        app.ViewerRenderResult(
            request_id=2,
            artifact_name="run.json",
            html="<html>run.json</html>",
            status_text="Viewing run.json.",
        )
    )

    app.ArtifactBrowserWindow._drain_pending_viewer_render(browser)

    assert browser.pending_viewer_artifact_name is None
    assert browser.rendered_viewer_artifact_name == "run.json"
    assert browser.status_output.text == "Viewing run.json."
    assert browser.viewer.html == "<html>run.json</html>"


def test_viewer_render_future_done_queues_result_and_wakes_ui(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    browser.viewer_render_results = Queue()
    awake_calls: list[str] = []
    result = app.ViewerRenderResult(
        request_id=1,
        artifact_name="run.json",
        html="<html>run.json</html>",
        status_text="Viewing run.json.",
    )

    monkeypatch.setattr(
        app,
        "fltk",
        SimpleNamespace(
            Fl=SimpleNamespace(awake=lambda: awake_calls.append("awake"))
        ),
    )

    future = SimpleNamespace(
        cancelled=lambda: False,
        result=lambda: result,
    )

    app.ArtifactBrowserWindow._on_viewer_render_future_done(browser, future)

    queued_result = browser.viewer_render_results.get_nowait()
    assert queued_result == result
    assert awake_calls == ["awake"]


def test_handle_viewer_link_renders_internal_source_snapshot(
    tmp_path: app.Path,
) -> None:
    assert hasattr(app.ArtifactBrowserWindow, "_handle_viewer_link")

    run_dir = tmp_path / "20260318T225654Z"
    run_dir.mkdir()
    html_path = run_dir / "digest.html"
    html_path.write_text("<html><body>Digest</body></html>\n", encoding="utf-8")
    _write_json(
        run_dir / "run.json",
        {
            "run_id": "20260318T225654Z",
            "digest_title": "Chip Race",
        },
    )
    _write_json(
        run_dir / "issues.json",
        [
            {
                "slug": "chip_race",
                "title": "Chip Race",
                "summary": "Supply constraints keep shaping AI infra.",
                "thread_ids": ["2032245601216389324"],
                "thread_count": 1,
            }
        ],
    )
    _write_json(run_dir / "issue_assignments.json", [_issue_thread_payload()])

    browser = object.__new__(app.ArtifactBrowserWindow)
    browser.viewer = FakeViewer()
    browser.status_output = FakeStatus()
    browser.selected_artifact_name = "digest.html"
    browser.artifacts = [
        ArtifactRecord(
            name="digest.html",
            path=html_path,
            kind="html",
            exists=True,
        )
    ]
    browser._current_theme = lambda: app.CLASSIC_LIGHT_THEME
    browser._set_viewer_html = lambda html: (
        browser.viewer.value(html),
        browser.viewer.topline(0),
        browser.viewer.leftline(0),
    )

    result = app.ArtifactBrowserWindow._handle_viewer_link(
        browser,
        browser.viewer,
        "xs2n://thread/2032245601216389324",
    )

    assert result is None
    assert "Digest / Chip Race / Foundry capacity is still the gating factor" in browser.viewer.html
    assert "Open on X" in browser.viewer.html
    assert browser.status_output.text == "Viewing source snapshot for Foundry capacity is still the gating factor."


def test_handle_viewer_link_opens_external_url_in_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert hasattr(app.ArtifactBrowserWindow, "_handle_viewer_link")

    opened_urls: list[str] = []
    monkeypatch.setattr(
        app.webbrowser,
        "open",
        lambda url: opened_urls.append(url) or True,
    )

    browser = object.__new__(app.ArtifactBrowserWindow)
    browser.viewer = FakeViewer()
    browser.status_output = FakeStatus()

    result = app.ArtifactBrowserWindow._handle_viewer_link(
        browser,
        browser.viewer,
        "https://x.com/realmcore_/status/2032245601216389324",
    )

    assert result is None
    assert opened_urls == ["https://x.com/realmcore_/status/2032245601216389324"]
    assert browser.status_output.text == "Opened source in your browser."

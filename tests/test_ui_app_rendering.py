from __future__ import annotations

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
        self.visible = True

    def value(self, html: str) -> None:
        self.html = html

    def topline(self, line: int) -> None:
        self.top = line

    def leftline(self, line: int) -> None:
        self.left = line

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False


class FakeStatus:
    def __init__(self) -> None:
        self.text = ""

    def value(self, text: str) -> None:
        self.text = text


class FakeDigestViewer:
    def __init__(self, *, load_result: bool = True) -> None:
        self.load_result = load_result
        self.loaded_run_dirs: list[app.Path] = []
        self.visible = False
        self.shown_overview = 0
        self.shown_threads: list[str] = []
        self.back_calls = 0

    def load_run(self, run_dir: app.Path) -> bool:
        self.loaded_run_dirs.append(run_dir)
        return self.load_result

    def show_overview(self) -> None:
        self.shown_overview += 1

    def show_thread(self, thread_id: str) -> None:
        self.shown_threads.append(thread_id)

    def go_back(self) -> None:
        self.back_calls += 1

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def resize(self, *_args) -> None:  # noqa: ANN001
        return None

    def apply_theme(self, _theme) -> None:  # noqa: ANN001
        return None


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


def test_apply_selected_artifact_name_routes_digest_html_to_native_viewer() -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    browser.artifacts = [
        ArtifactRecord(
            name="digest.html",
            path=app.Path("data/report_runs/demo/digest.html"),
            kind="html",
            exists=True,
        )
    ]
    browser.sections = [
        ArtifactSectionRecord(
            icon="◆",
            label="Digest",
            artifact_name="digest.html",
        )
    ]
    browser.sections_browser = FakeBrowser()
    browser.raw_files_browser = FakeBrowser()
    browser.viewer = FakeViewer()
    browser.digest_viewer = FakeDigestViewer(load_result=True)
    browser.status_output = FakeStatus()
    browser.viewer_render_results = Queue()
    browser.selected_artifact_name = None
    browser.pending_viewer_artifact_name = None
    browser.rendered_viewer_artifact_name = None
    browser.pending_viewer_request_id = 0
    browser.viewer_render_future = None
    browser._schedule_artifact_preview_render = lambda artifact: (_ for _ in ()).throw(
        AssertionError("digest viewer should not schedule generic preview render")
    )

    app.ArtifactBrowserWindow._apply_selected_artifact_name(browser, "digest.html")

    assert browser.selected_artifact_name == "digest.html"
    assert browser.digest_viewer.loaded_run_dirs == [app.Path("data/report_runs/demo")]
    assert browser.digest_viewer.shown_overview == 1
    assert browser.digest_viewer.visible is True
    assert browser.viewer.visible is False
    assert browser.pending_viewer_artifact_name is None
    assert browser.status_output.text == "Viewing digest overview."


def test_apply_selected_artifact_name_falls_back_when_digest_viewer_cannot_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    browser.artifacts = [
        ArtifactRecord(
            name="digest.html",
            path=app.Path("data/report_runs/demo/digest.html"),
            kind="html",
            exists=True,
        )
    ]
    browser.sections = []
    browser.sections_browser = FakeBrowser()
    browser.raw_files_browser = FakeBrowser()
    browser.viewer = FakeViewer()
    browser.digest_viewer = FakeDigestViewer(load_result=False)
    browser.status_output = FakeStatus()
    browser.viewer_render_results = Queue()
    browser.selected_artifact_name = None
    browser.pending_viewer_artifact_name = None
    browser.rendered_viewer_artifact_name = None
    browser.pending_viewer_request_id = 0
    browser.viewer_render_future = None
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

    app.ArtifactBrowserWindow._apply_selected_artifact_name(browser, "digest.html")

    assert browser.digest_viewer.loaded_run_dirs == [app.Path("data/report_runs/demo")]
    assert browser.viewer.visible is True
    assert browser.digest_viewer.visible is False
    assert browser.viewer.html == "<loading>digest.html</loading>"
    assert scheduled_artifacts == ["digest.html"]


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

from __future__ import annotations

import io
from queue import Queue
from types import SimpleNamespace
import signal

import xs2n.ui.app as app
from xs2n.schemas.auth import AuthDoctorResult, ProviderStatus, RunReadiness
from xs2n.schemas.run_events import RunEvent
from xs2n.ui.artifacts import ArtifactRecord, ArtifactSectionRecord, RunRecord
from xs2n.ui.run_arguments import RunCommand


def test_run_browser_event_loop_closes_browser_on_sigint(
    monkeypatch,
) -> None:
    idle_callbacks = []
    installed_handlers: list[object] = []
    previous_sigint_handler = object()
    close_calls: list[str] = []

    def fake_getsignal(signum: signal.Signals) -> object:
        assert signum is signal.SIGINT
        return previous_sigint_handler

    def fake_signal(signum: signal.Signals, handler: object) -> None:
        assert signum is signal.SIGINT
        installed_handlers.append(handler)

    class FakeFl:
        @staticmethod
        def add_idle(callback) -> None:  # noqa: ANN001
            idle_callbacks.append(callback)

        @staticmethod
        def remove_idle(callback) -> None:  # noqa: ANN001
            assert callback is idle_callbacks[0]

        @staticmethod
        def run() -> None:
            installed_handlers[0](signal.SIGINT, None)
            idle_callbacks[0](None)

    monkeypatch.setattr(app.signal, "getsignal", fake_getsignal)
    monkeypatch.setattr(app.signal, "signal", fake_signal)
    monkeypatch.setattr(app, "fltk", SimpleNamespace(Fl=FakeFl))

    app._run_browser_event_loop(
        close_browser=lambda: close_calls.append("closed"),
    )

    assert close_calls == ["closed"]
    assert installed_handlers == [installed_handlers[0], previous_sigint_handler]


def test_preferences_menu_shows_preferences_window() -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    show_calls: list[str] = []
    browser.preferences_window = SimpleNamespace(show=lambda: show_calls.append("show"))

    app.ArtifactBrowserWindow._on_preferences_clicked(browser)

    assert show_calls == ["show"]


def test_init_does_not_refresh_auth_state_automatically(monkeypatch) -> None:
    refresh_calls: list[str] = []

    class FakeWindow:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

    monkeypatch.setattr(
        app,
        "fltk",
        SimpleNamespace(
            Fl=SimpleNamespace(add_idle=lambda callback: None),
            Fl_Double_Window=lambda *args, **kwargs: FakeWindow(*args, **kwargs),
        ),
    )
    monkeypatch.setattr(
        app,
        "RunPreferencesWindow",
        lambda **kwargs: SimpleNamespace(
            current_run_list_column_keys=lambda: ("started_at", "digest_title"),
            apply_theme=lambda theme: None,
            hide=lambda: None,
        ),
    )
    monkeypatch.setattr(
        app,
        "AuthWindow",
        lambda **kwargs: SimpleNamespace(
            apply_theme=lambda theme: None,
            hide=lambda: None,
        ),
    )
    monkeypatch.setattr(
        app.ArtifactBrowserWindow,
        "_build_window",
        lambda self: None,
    )
    monkeypatch.setattr(
        app.ArtifactBrowserWindow,
        "_apply_theme_to_widgets",
        lambda self: None,
    )
    monkeypatch.setattr(
        app.ArtifactBrowserWindow,
        "refresh_runs",
        lambda self: None,
    )
    monkeypatch.setattr(
        app.ArtifactBrowserWindow,
        "_refresh_auth_state",
        lambda self: refresh_calls.append("refresh"),
    )
    monkeypatch.setattr(
        app,
        "load_ui_state",
        lambda path=None: {"appearance_mode": "system"},
    )
    monkeypatch.setattr(
        app,
        "resolve_ui_theme",
        lambda mode: app.CLASSIC_LIGHT_THEME,
    )
    monkeypatch.setattr(
        app,
        "apply_fltk_theme_defaults",
        lambda fltk_module, theme: None,
    )

    app.ArtifactBrowserWindow(data_dir=app.Path("data"))

    assert refresh_calls == []


def test_run_digest_click_starts_auth_preflight() -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    captured: list[tuple[RunCommand, str | None]] = []
    command = RunCommand(label="report issues", args=["report", "issues"])
    browser.preferences_window = SimpleNamespace(
        current_digest_command=lambda: command
    )
    browser._refresh_auth_state = lambda **kwargs: captured.append(
        (kwargs["pending_command"], kwargs.get("starting_status"))
    )

    app.ArtifactBrowserWindow._on_run_digest_clicked(browser)

    assert captured == [
        (
            command,
            "Checking authentication before report issues...",
        )
    ]


def test_latest_is_the_only_primary_run_action_in_the_toolbar_contract() -> None:
    assert app.PRIMARY_RUN_BUTTON_SYMBOL == "@>"
    assert app.PRIMARY_RUN_BUTTON_TOOLTIP == (
        "Run the configured `xs2n report latest` command."
    )
    assert app.RUN_MENU_LAUNCH_LABELS == (
        "&Run/&Refresh Following Sources",
        "&Run/&Latest 24h",
    )


def test_run_latest_click_surfaces_form_validation_error(monkeypatch) -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    alerts: list[str] = []

    show_latest_calls: list[str] = []
    browser.preferences_window = SimpleNamespace(
        current_latest_command=lambda: (_ for _ in ()).throw(
            ValueError("Lookback hours must be at least 1.")
        ),
        show_latest_tab=lambda: show_latest_calls.append("latest"),
    )
    browser._start_run_command = lambda command: (_ for _ in ()).throw(
        AssertionError("should not start command")
    )

    monkeypatch.setattr(
        app,
        "fltk",
        SimpleNamespace(fl_alert=lambda message: alerts.append(message)),
    )

    app.ArtifactBrowserWindow._on_run_latest_clicked(browser)

    assert alerts == ["Lookback hours must be at least 1."]
    assert show_latest_calls == ["latest"]


def test_handle_run_auth_doctor_result_blocks_latest_when_x_is_missing() -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    started: list[RunCommand] = []
    status_messages: list[str] = []
    auth_updates: list[tuple[AuthDoctorResult, object]] = []
    auth_window_shown: list[str] = []
    browser.status_output = SimpleNamespace(
        value=lambda text: status_messages.append(text)
    )
    browser.auth_window = SimpleNamespace(
        update_snapshot=lambda *, snapshot, cookies_file: auth_updates.append(
            (snapshot, cookies_file)
        ),
        show=lambda: auth_window_shown.append("show"),
    )
    browser._start_run_command = lambda command: started.append(command)
    browser._current_cookies_file = lambda: app.Path("tmp/cookies.json")

    snapshot = AuthDoctorResult(
        codex=ProviderStatus(
            status="ready",
            summary="Codex credentials available.",
            detail=None,
        ),
        x=ProviderStatus(
            status="missing",
            summary="Missing X session.",
            detail=None,
        ),
        run_readiness=RunReadiness(
            digest_ready=True,
            latest_ready=False,
        ),
    )
    command = RunCommand(label="report latest", args=["report", "latest"])

    app.ArtifactBrowserWindow._handle_run_auth_doctor_result(
        browser,
        snapshot=snapshot,
        command=command,
    )

    assert started == []
    assert auth_window_shown == ["show"]
    assert auth_updates == [(snapshot, app.Path("tmp/cookies.json"))]
    assert status_messages == [
        "Cannot start report latest until Codex and X / Twitter are ready."
    ]


def test_drain_idle_work_applies_streamed_run_events() -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    refresh_calls: list[str] = []

    browser.command_progress_updates = Queue()
    browser.command_results = Queue()
    browser.viewer_render_results = Queue()
    browser.running_label = None
    browser.running_thread = None
    browser.selected_run_id = None
    browser.status_output = FakeStatusOutput()
    browser.refresh_runs = lambda: refresh_calls.append("refresh")
    browser._drain_pending_viewer_render = lambda: None
    browser._sync_run_list_layout = lambda force=False: None

    browser.command_progress_updates.put(
        app.CommandProgress(
            label="report latest",
            event=RunEvent(
                event="run_started",
                message="Issue run 20260319T101500Z started.",
                run_id="20260319T101500Z",
            ),
        )
    )
    browser.command_progress_updates.put(
        app.CommandProgress(
            label="report latest",
            event=RunEvent(
                event="artifact_written",
                message="Wrote filtered threads artifact.",
                run_id="20260319T101500Z",
                phase="filter_threads",
                artifact_path="data/report_runs/20260319T101500Z/filtered_threads.json",
            ),
        )
    )

    app.ArtifactBrowserWindow._drain_idle_work(browser)

    assert browser.selected_run_id == "20260319T101500Z"
    assert refresh_calls == ["refresh"]
    assert browser.status_output.messages[-1] == "Wrote filtered threads artifact."


def test_start_command_streams_jsonl_events_with_popen(monkeypatch) -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    viewer_html: list[str] = []

    browser.running_label = None
    browser.running_thread = None
    browser.repo_root = app.Path("/tmp/xs2n")
    browser.cli_executable = "xs2n"
    browser.command_progress_updates = Queue()
    browser.command_results = Queue()
    browser.status_output = FakeStatusOutput()
    browser._clear_artifact_viewer_state = lambda: None
    browser._set_viewer_html = lambda html: viewer_html.append(html)
    browser._current_theme = lambda: app.CLASSIC_LIGHT_THEME
    browser._wake_ui = lambda: None

    class InlineThread:
        def __init__(self, *, target, daemon=None) -> None:  # noqa: ANN001
            self._target = target
            self._alive = False

        def start(self) -> None:
            self._alive = True
            self._target()
            self._alive = False

        def is_alive(self) -> bool:
            return self._alive

        def join(self) -> None:
            return None

    class FakePopen:
        def __init__(self, command, cwd, text, stdout, stderr, bufsize) -> None:  # noqa: ANN001
            self.command = command
            self.cwd = cwd
            self.returncode = 0
            self.stdout = io.StringIO(
                '{"event":"run_started","message":"Issue run 20260319T101500Z started.","run_id":"20260319T101500Z"}\n'
                '{"event":"artifact_written","message":"Wrote issues artifact.","run_id":"20260319T101500Z","artifact_path":"data/report_runs/20260319T101500Z/issues.json"}\n'
            )
            self.stderr = io.StringIO("human log\n")

        def wait(self) -> int:
            return self.returncode

    monkeypatch.setattr(app.threading, "Thread", InlineThread)
    monkeypatch.setattr(app.subprocess, "Popen", FakePopen)

    app.ArtifactBrowserWindow._start_command(
        browser,
        label="report latest",
        args=["report", "latest", "--jsonl-events"],
        stream_jsonl_events=True,
    )

    progress = browser.command_progress_updates.get_nowait()
    result = browser.command_results.get_nowait()

    assert progress.event.event == "run_started"
    assert result.returncode == 0
    assert "artifact_written" in result.stdout
    assert "human log" in result.stderr
    assert viewer_html


def test_apply_selected_artifact_name_syncs_sections_and_raw_files(
    monkeypatch,
) -> None:
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
        lambda artifact, *, theme=None: f"<loading>{artifact.name}</loading>",
    )

    app.ArtifactBrowserWindow._apply_selected_artifact_name(
        browser,
        "run.json",
    )

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

    app.ArtifactBrowserWindow._apply_selected_artifact_name(
        browser,
        "llm_calls/001_trace.json",
    )

    assert browser.sections_browser.selection == 0
    assert browser.raw_files_browser.selection == 3
    assert browser.pending_viewer_artifact_name == "llm_calls/001_trace.json"
    assert scheduled_artifacts == ["run.json", "llm_calls/001_trace.json"]


def test_drain_pending_viewer_render_uses_latest_completed_result(
) -> None:
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
    monkeypatch,
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

    app.ArtifactBrowserWindow._on_viewer_render_future_done(
        browser,
        future,
    )

    queued_result = browser.viewer_render_results.get_nowait()
    assert queued_result == result
    assert awake_calls == ["awake"]


def test_viewer_render_future_error_keeps_original_request_identity(
    monkeypatch,
) -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    browser.viewer_render_results = Queue()
    browser.pending_viewer_request_id = 2
    browser.selected_artifact_name = "run.json"

    monkeypatch.setattr(
        app,
        "fltk",
        SimpleNamespace(
            Fl=SimpleNamespace(awake=lambda: None)
        ),
    )

    future = SimpleNamespace(
        request_id=1,
        artifact_name="digest.md",
        cancelled=lambda: False,
        result=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    app.ArtifactBrowserWindow._on_viewer_render_future_done(
        browser,
        future,
    )

    queued_result = browser.viewer_render_results.get_nowait()
    assert queued_result.request_id == 1
    assert queued_result.artifact_name == "digest.md"
    assert queued_result.status_text == "Failed to render digest.md."


def test_run_list_preferences_change_refreshes_rows_and_layout() -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    selected_rows: list[int] = []
    status_messages: list[str] = []
    refreshed: list[str] = []
    synced: list[bool] = []

    browser.runs = [
        RunRecord(
            root_name="report_runs",
            run_id="20260315T203138Z",
            run_dir=app.Path("data/report_runs/20260315T203138Z"),
        )
    ]
    browser.runs_browser = SimpleNamespace(
        value=lambda selection=None: selected_rows.append(selection)
        if selection is not None
        else 0
    )
    browser.status_output = SimpleNamespace(
        value=lambda text: status_messages.append(text)
    )
    browser._refresh_run_list_rows = lambda: refreshed.append("rows")
    browser._resolve_selected_run_index = lambda: 0
    browser._sync_run_list_layout = lambda force=False: synced.append(force)

    app.ArtifactBrowserWindow._on_run_list_preferences_changed(
        browser,
        ("started_at", "digest_title", "status"),
    )

    assert browser.run_list_column_keys == (
        "started_at",
        "digest_title",
        "status",
    )
    assert refreshed == ["rows"]
    assert selected_rows == [1]
    assert synced == [True]
    assert status_messages == ["Run list columns updated."]


def test_appearance_mode_change_resolves_theme_saves_state_and_refreshes(
    monkeypatch,
) -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    browser.appearance_mode = "system"
    browser.theme = object()
    browser.preferences_window = SimpleNamespace(
        apply_theme=lambda theme: themed_preferences.append(theme)
    )
    browser.refresh_runs = lambda: refreshed.append("refresh")
    browser._apply_theme_to_widgets = lambda: themed_widgets.append("widgets")

    themed_preferences: list[object] = []
    themed_widgets: list[str] = []
    refreshed: list[str] = []
    saved_states: list[dict[str, str]] = []
    applied_defaults: list[object] = []
    dark_theme = SimpleNamespace(name="classic_dark")

    monkeypatch.setattr(
        app,
        "save_ui_state",
        lambda state, path=None: saved_states.append(state),
    )
    monkeypatch.setattr(
        app,
        "resolve_ui_theme",
        lambda mode: dark_theme,
    )
    monkeypatch.setattr(
        app,
        "apply_fltk_theme_defaults",
        lambda fltk_module, theme: applied_defaults.append(theme),
    )

    app.ArtifactBrowserWindow._on_appearance_mode_changed(
        browser,
        "classic_dark",
    )

    assert browser.appearance_mode == "classic_dark"
    assert browser.theme == dark_theme
    assert saved_states == [{"appearance_mode": "classic_dark"}]
    assert applied_defaults == [dark_theme]
    assert themed_widgets == ["widgets"]
    assert themed_preferences == [dark_theme]
    assert refreshed == ["refresh"]


def test_delete_selected_runs_confirms_refreshes_and_sets_fallback_run(
    monkeypatch,
) -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    deleted_run_ids: list[str] = []
    prompts: list[str] = []
    refresh_calls: list[str] = []

    browser.running_label = None
    browser.running_thread = None
    browser.selected_artifact_name = "digest.md"
    browser.runs = [
        RunRecord(
            root_name="report_runs",
            run_id="20260315T203138Z",
            run_dir=app.Path("data/report_runs/20260315T203138Z"),
        ),
        RunRecord(
            root_name="report_runs",
            run_id="20260315T203500Z",
            run_dir=app.Path("data/report_runs/20260315T203500Z"),
        ),
        RunRecord(
            root_name="report_runs",
            run_id="20260315T203900Z",
            run_dir=app.Path("data/report_runs/20260315T203900Z"),
        ),
    ]
    browser.runs_browser = SimpleNamespace(
        selected=lambda line_number: line_number in {1, 2},
        value=lambda selection=None: 2 if selection is None else selection,
    )
    browser.status_output = FakeStatusOutput()
    browser.refresh_runs = lambda: refresh_calls.append("refresh")

    monkeypatch.setattr(
        app,
        "delete_runs",
        lambda runs: deleted_run_ids.extend(run.run_id for run in runs),
    )
    monkeypatch.setattr(
        app,
        "fltk",
        SimpleNamespace(
            fl_alert=lambda message: (_ for _ in ()).throw(
                AssertionError(message)
            ),
            fl_choice=lambda message, b0, b1, b2: prompts.append(message) or 1,
        ),
    )

    app.ArtifactBrowserWindow._on_delete_selected_runs_requested(browser)

    assert deleted_run_ids == ["20260315T203138Z", "20260315T203500Z"]
    assert browser.selected_run_id == "20260315T203900Z"
    assert browser.selected_artifact_name is None
    assert refresh_calls == ["refresh"]
    assert browser.status_output.messages == ["Deleted 2 runs."]
    assert "Delete 2 selected runs from disk?" in prompts[0]


def test_delete_selected_runs_respects_cancel(monkeypatch) -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    refresh_calls: list[str] = []

    browser.running_label = None
    browser.running_thread = None
    browser.selected_artifact_name = "digest.md"
    browser.runs = [
        RunRecord(
            root_name="report_runs",
            run_id="20260315T203138Z",
            run_dir=app.Path("data/report_runs/20260315T203138Z"),
        )
    ]
    browser.runs_browser = SimpleNamespace(
        selected=lambda line_number: line_number == 1,
        value=lambda selection=None: 1 if selection is None else selection,
    )
    browser.status_output = FakeStatusOutput()
    browser.refresh_runs = lambda: refresh_calls.append("refresh")

    monkeypatch.setattr(
        app,
        "delete_runs",
        lambda runs: (_ for _ in ()).throw(
            AssertionError("delete should not run")
        ),
    )
    monkeypatch.setattr(
        app,
        "fltk",
        SimpleNamespace(
            fl_alert=lambda message: (_ for _ in ()).throw(
                AssertionError(message)
            ),
            fl_choice=lambda message, b0, b1, b2: 0,
        ),
    )

    app.ArtifactBrowserWindow._on_delete_selected_runs_requested(browser)

    assert refresh_calls == []
    assert browser.status_output.messages == []


def test_delete_selected_runs_alerts_when_nothing_is_selected(monkeypatch) -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    alerts: list[str] = []

    browser.running_label = None
    browser.running_thread = None
    browser.runs = [
        RunRecord(
            root_name="report_runs",
            run_id="20260315T203138Z",
            run_dir=app.Path("data/report_runs/20260315T203138Z"),
        )
    ]
    browser.runs_browser = SimpleNamespace(
        selected=lambda line_number: False,
        value=lambda selection=None: 0 if selection is None else selection,
    )
    browser.status_output = FakeStatusOutput()

    monkeypatch.setattr(
        app,
        "fltk",
        SimpleNamespace(
            fl_alert=lambda message: alerts.append(message),
            fl_choice=lambda message, b0, b1, b2: (_ for _ in ()).throw(
                AssertionError("choice should not open")
            ),
        ),
    )

    app.ArtifactBrowserWindow._on_delete_selected_runs_requested(browser)

    assert alerts == ["Select at least one run to delete."]


class FakeGeometryWidget:
    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        self._x = x
        self._y = y
        self._width = width
        self._height = height
        self.hidden = False
        self.redraw_calls = 0
        self.init_sizes_calls = 0

    def x(self) -> int:
        return self._x

    def y(self) -> int:
        return self._y

    def w(self) -> int:
        return self._width

    def h(self) -> int:
        return self._height

    def resize(self, x: int, y: int, width: int, height: int) -> None:
        self._x = x
        self._y = y
        self._width = width
        self._height = height

    def hide(self) -> None:
        self.hidden = True

    def show(self) -> None:
        self.hidden = False

    def redraw(self) -> None:
        self.redraw_calls += 1

    def init_sizes(self) -> None:
        self.init_sizes_calls += 1


class FakeToggleWidget:
    def __init__(self) -> None:
        self.current_value = 0
        self.current_tooltip = ""
        self.redraw_calls = 0

    def value(self, new_value: int | None = None) -> int:
        if new_value is None:
            return self.current_value
        self.current_value = new_value
        return self.current_value

    def tooltip(self, new_tooltip: str | None = None) -> str:
        if new_tooltip is None:
            return self.current_tooltip
        self.current_tooltip = new_tooltip
        return self.current_tooltip

    def redraw(self) -> None:
        self.redraw_calls += 1


class FakeStatusOutput:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def value(self, text: str) -> None:
        self.messages.append(text)


def test_set_focus_mode_shows_only_viewer_and_restores_layout() -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    synced: list[bool] = []
    browser.focus_mode_enabled = False
    browser.standard_pane_widths = (app.LEFT_PANE_WIDTH, app.MIDDLE_PANE_WIDTH)
    browser.tile = FakeGeometryWidget(0, 68, 1480, 828)
    browser.run_list_group = FakeGeometryWidget(0, 68, 380, 828)
    browser.run_list_header_background = FakeGeometryWidget(0, 68, 380, 24)
    browser.runs_browser = FakeGeometryWidget(0, 92, 380, 804)
    browser.navigation_group = FakeGeometryWidget(380, 68, 340, 828)
    browser.sections_header = FakeGeometryWidget(380, 68, 340, 24)
    browser.sections_browser = FakeGeometryWidget(380, 92, 340, 188)
    browser.raw_files_header = FakeGeometryWidget(380, 288, 340, 24)
    browser.raw_files_browser = FakeGeometryWidget(380, 312, 340, 584)
    browser.viewer = FakeGeometryWidget(720, 68, 760, 828)
    browser.focus_mode_button = FakeToggleWidget()
    browser.status_output = FakeStatusOutput()
    browser._sync_run_list_layout = lambda force=False: synced.append(force)

    app.ArtifactBrowserWindow._set_focus_mode(browser, enabled=True)

    assert browser.focus_mode_enabled is True
    assert browser.standard_pane_widths == (380, 340)
    assert browser.run_list_group.hidden is True
    assert browser.navigation_group.hidden is True
    assert (
        browser.viewer.x(),
        browser.viewer.y(),
        browser.viewer.w(),
        browser.viewer.h(),
    ) == (0, 68, 1480, 828)
    assert browser.focus_mode_button.value() == 1
    assert "restore the run and navigation panes" in browser.focus_mode_button.tooltip()
    assert browser.tile.init_sizes_calls == 1
    assert browser.tile.redraw_calls == 1
    assert synced == []
    assert browser.status_output.messages[-1] == (
        "Focus mode enabled. Showing the viewer only."
    )

    browser.tile.resize(0, 68, 1600, 860)

    app.ArtifactBrowserWindow._set_focus_mode(browser, enabled=False)

    assert browser.focus_mode_enabled is False
    assert browser.run_list_group.hidden is False
    assert browser.navigation_group.hidden is False
    assert (
        browser.run_list_group.x(),
        browser.run_list_group.y(),
        browser.run_list_group.w(),
        browser.run_list_group.h(),
    ) == (0, 68, 380, 860)
    assert (
        browser.navigation_group.x(),
        browser.navigation_group.y(),
        browser.navigation_group.w(),
        browser.navigation_group.h(),
    ) == (380, 68, 340, 860)
    assert (
        browser.viewer.x(),
        browser.viewer.y(),
        browser.viewer.w(),
        browser.viewer.h(),
    ) == (720, 68, 880, 860)
    assert browser.raw_files_browser.h() == 612
    assert browser.focus_mode_button.value() == 0
    assert "show only the viewer pane" in browser.focus_mode_button.tooltip()
    assert browser.tile.init_sizes_calls == 2
    assert browser.tile.redraw_calls == 2
    assert synced == [True]
    assert browser.status_output.messages[-1] == (
        "Focus mode disabled. Restored all three panes."
    )


def test_close_browser_warns_if_run_is_still_active_and_user_stays(
    monkeypatch,
) -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    hide_calls: list[str] = []
    prompts: list[str] = []
    browser.running_label = "report digest"
    browser.running_thread = SimpleNamespace(is_alive=lambda: True)
    browser.preferences_window = SimpleNamespace(
        hide=lambda: hide_calls.append("preferences")
    )
    browser.window = SimpleNamespace(hide=lambda: hide_calls.append("window"))

    monkeypatch.setattr(
        app,
        "fltk",
        SimpleNamespace(
            fl_choice=lambda message, b0, b1, b2: prompts.append(message) or 0,
            Fl=SimpleNamespace(
                hide_all_windows=lambda: hide_calls.append("all_windows")
            ),
        ),
    )

    app.ArtifactBrowserWindow.close_browser(browser)

    assert hide_calls == []
    assert prompts == [
        "`report digest` is still running.\nQuit the UI anyway? The run may be interrupted."
    ]


def test_close_browser_quits_after_confirmation_when_run_is_active(
    monkeypatch,
) -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    hide_calls: list[str] = []
    browser.running_label = "report digest"
    browser.running_thread = SimpleNamespace(is_alive=lambda: True)
    browser.preferences_window = SimpleNamespace(
        hide=lambda: hide_calls.append("preferences")
    )
    browser.window = SimpleNamespace(hide=lambda: hide_calls.append("window"))

    monkeypatch.setattr(
        app,
        "fltk",
        SimpleNamespace(
            fl_choice=lambda message, b0, b1, b2: 1,
            Fl=SimpleNamespace(
                hide_all_windows=lambda: hide_calls.append("all_windows")
            ),
        ),
    )

    app.ArtifactBrowserWindow.close_browser(browser)

    assert hide_calls == ["preferences", "window", "all_windows"]


def test_focus_mode_toggle_reads_button_state() -> None:
    browser = object.__new__(app.ArtifactBrowserWindow)
    recorded_states: list[bool] = []
    browser._set_focus_mode = lambda *, enabled: recorded_states.append(enabled)

    app.ArtifactBrowserWindow._on_focus_mode_toggled(
        browser,
        SimpleNamespace(value=lambda: 1),
    )
    app.ArtifactBrowserWindow._on_focus_mode_toggled(
        browser,
        SimpleNamespace(value=lambda: 0),
    )

    assert recorded_states == [True, False]

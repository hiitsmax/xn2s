from __future__ import annotations

from types import SimpleNamespace

from xs2n.ui.run_arguments import (
    IssuesRunArguments,
    LatestRunArguments,
    RunCommand,
)
from xs2n.ui.run_preferences import RunPreferencesWindow
from xs2n.ui.run_list import DEFAULT_RUN_LIST_COLUMN_KEYS


class FakeValueWidget:
    def __init__(self, value) -> None:  # noqa: ANN001
        self._value = value

    def value(self, new_value=None):  # noqa: ANN001
        if new_value is None:
            return self._value
        self._value = new_value
        return self._value


def test_current_digest_command_uses_last_applied_values() -> None:
    window = object.__new__(RunPreferencesWindow)
    window.applied_digest_arguments = IssuesRunArguments.from_form(
        timeline_file="tmp/timeline.json",
        output_dir="tmp/report_runs",
        model="gpt-5.5",
    )

    command = RunPreferencesWindow.current_digest_command(window)

    assert command == RunCommand(
        label="report issues",
        args=[
            "report",
            "issues",
            "--timeline-file",
            "tmp/timeline.json",
            "--output-dir",
            "tmp/report_runs",
            "--model",
            "gpt-5.5",
            "--jsonl-events",
        ],
        stream_jsonl_events=True,
    )


def test_current_latest_command_uses_last_applied_values() -> None:
    window = object.__new__(RunPreferencesWindow)
    window.applied_latest_arguments = LatestRunArguments.from_form(
        since="2026-03-15T20:31:38Z",
        lookback_hours="12",
        cookies_file="tmp/cookies.json",
        limit="150",
        timeline_file="tmp/timeline.json",
        sources_file="tmp/sources.json",
        home_latest=True,
        output_dir="tmp/report_runs",
        model="gpt-5.5-mini",
    )

    command = RunPreferencesWindow.current_latest_command(window)

    assert command == RunCommand(
        label="report latest",
        args=[
            "report",
            "latest",
            "--lookback-hours",
            "12",
            "--cookies-file",
            "tmp/cookies.json",
            "--limit",
            "150",
            "--timeline-file",
            "tmp/timeline.json",
            "--sources-file",
            "tmp/sources.json",
            "--output-dir",
            "tmp/report_runs",
            "--model",
            "gpt-5.5-mini",
            "--jsonl-events",
            "--since",
            "2026-03-15T20:31:38Z",
            "--home-latest",
        ],
        stream_jsonl_events=True,
    )


def test_show_latest_tab_selects_tab_and_shows_window() -> None:
    window = object.__new__(RunPreferencesWindow)
    calls: list[object] = []
    window.latest_tab = object()
    window.tabs = SimpleNamespace(value=lambda tab: calls.append(tab))
    window.window = SimpleNamespace(show=lambda: calls.append("show"))

    RunPreferencesWindow.show_latest_tab(window)

    assert calls == [window.latest_tab, "show"]


def test_current_run_list_column_keys_returns_last_applied_columns() -> None:
    window = object.__new__(RunPreferencesWindow)
    window.applied_run_list_column_keys = ("started_at", "digest_title", "status")

    assert RunPreferencesWindow.current_run_list_column_keys(window) == (
        "started_at",
        "digest_title",
        "status",
    )


def test_current_appearance_mode_returns_last_applied_value() -> None:
    window = object.__new__(RunPreferencesWindow)
    window.applied_appearance_mode = "classic_dark"

    assert RunPreferencesWindow.current_appearance_mode(window) == "classic_dark"


def test_current_digest_navigation_visible_returns_last_applied_value() -> None:
    window = object.__new__(RunPreferencesWindow)
    window.applied_digest_navigation_visible = True

    assert RunPreferencesWindow.current_digest_navigation_visible(window) is True


def test_apply_click_commits_draft_values_without_live_updates() -> None:
    window = object.__new__(RunPreferencesWindow)
    changes: list[tuple[str, ...]] = []
    appearance_changes: list[str] = []
    digest_navigation_changes: list[bool] = []
    window.on_run_list_preferences_changed = lambda keys: changes.append(keys)
    window.on_appearance_mode_changed = (
        lambda mode: appearance_changes.append(mode)
    )
    window.on_digest_navigation_preference_changed = (
        lambda visible: digest_navigation_changes.append(visible)
    )
    window.applied_digest_arguments = IssuesRunArguments()
    window.applied_latest_arguments = LatestRunArguments()
    window.applied_run_list_column_keys = DEFAULT_RUN_LIST_COLUMN_KEYS
    window.applied_appearance_mode = "system"
    window.applied_digest_navigation_visible = False
    window.digest_timeline_input = FakeValueWidget("tmp/timeline.json")
    window.digest_output_dir_input = FakeValueWidget("tmp/report_runs")
    window.digest_model_input = FakeValueWidget("gpt-5.5")
    window.latest_since_input = FakeValueWidget("2026-03-15T20:31:38Z")
    window.latest_lookback_hours_input = FakeValueWidget("12")
    window.latest_cookies_file_input = FakeValueWidget("tmp/cookies.json")
    window.latest_limit_input = FakeValueWidget("150")
    window.latest_timeline_file_input = FakeValueWidget("tmp/timeline.json")
    window.latest_sources_file_input = FakeValueWidget("tmp/sources.json")
    window.latest_home_latest_toggle = FakeValueWidget(1)
    window.latest_output_dir_input = FakeValueWidget("tmp/report_runs")
    window.latest_model_input = FakeValueWidget("gpt-5.5-mini")
    window.appearance_mode_choice = FakeValueWidget("classic_dark")
    window.digest_navigation_toggle = FakeValueWidget(1)
    window.run_list_column_toggles = {
        "started_at": FakeValueWidget(1),
        "digest_title": FakeValueWidget(1),
        "root_name": FakeValueWidget(0),
        "status": FakeValueWidget(0),
        "model": FakeValueWidget(1),
        "count_triplet": FakeValueWidget(0),
        "run_id": FakeValueWidget(0),
    }

    assert RunPreferencesWindow.current_digest_command(window) == RunCommand(
        label="report issues",
        args=[
            "report",
            "issues",
            "--timeline-file",
            "data/timeline.json",
            "--output-dir",
            "data/report_runs",
            "--model",
            "gpt-5.4-mini",
            "--jsonl-events",
        ],
        stream_jsonl_events=True,
    )

    RunPreferencesWindow._on_apply_clicked(window)

    assert changes == [("started_at", "digest_title", "model")]
    assert appearance_changes == ["classic_dark"]
    assert digest_navigation_changes == [True]
    assert RunPreferencesWindow.current_digest_command(window) == RunCommand(
        label="report issues",
        args=[
            "report",
            "issues",
            "--timeline-file",
            "tmp/timeline.json",
            "--output-dir",
            "tmp/report_runs",
            "--model",
            "gpt-5.5",
            "--jsonl-events",
        ],
        stream_jsonl_events=True,
    )
    latest_args = RunPreferencesWindow.current_latest_command(window).args
    assert "--since" in latest_args
    assert "--home-latest" in latest_args
    assert RunPreferencesWindow.current_run_list_column_keys(window) == (
        "started_at",
        "digest_title",
        "model",
    )
    assert RunPreferencesWindow.current_appearance_mode(window) == "classic_dark"
    assert RunPreferencesWindow.current_digest_navigation_visible(window) is True


def test_cancel_discards_unsaved_draft_values() -> None:
    window = object.__new__(RunPreferencesWindow)
    hide_calls: list[str] = []
    window.window = SimpleNamespace(hide=lambda: hide_calls.append("hide"))
    window.applied_digest_arguments = IssuesRunArguments.from_form(
        timeline_file="data/timeline.json",
        output_dir="data/report_runs",
        model="gpt-5.4-mini",
    )
    window.applied_latest_arguments = LatestRunArguments()
    window.applied_run_list_column_keys = ("started_at", "status")
    window.applied_appearance_mode = "classic_light"
    window.applied_digest_navigation_visible = False
    window.digest_timeline_input = FakeValueWidget("tmp/timeline.json")
    window.digest_output_dir_input = FakeValueWidget("tmp/report_runs")
    window.digest_model_input = FakeValueWidget("gpt-5.5")
    window.latest_since_input = FakeValueWidget("2026-03-15T20:31:38Z")
    window.latest_lookback_hours_input = FakeValueWidget("12")
    window.latest_cookies_file_input = FakeValueWidget("tmp/cookies.json")
    window.latest_limit_input = FakeValueWidget("150")
    window.latest_timeline_file_input = FakeValueWidget("tmp/timeline.json")
    window.latest_sources_file_input = FakeValueWidget("tmp/sources.json")
    window.latest_home_latest_toggle = FakeValueWidget(1)
    window.latest_output_dir_input = FakeValueWidget("tmp/report_runs")
    window.latest_model_input = FakeValueWidget("gpt-5.5-mini")
    window.appearance_mode_choice = FakeValueWidget("classic_dark")
    window.digest_navigation_toggle = FakeValueWidget(1)
    window.run_list_column_toggles = {
        "started_at": FakeValueWidget(1),
        "digest_title": FakeValueWidget(1),
        "root_name": FakeValueWidget(0),
        "status": FakeValueWidget(0),
        "model": FakeValueWidget(1),
        "count_triplet": FakeValueWidget(0),
        "run_id": FakeValueWidget(0),
    }

    RunPreferencesWindow._on_cancel_clicked(window)

    assert hide_calls == ["hide"]
    assert window.digest_timeline_input.value() == "data/timeline.json"
    assert window.digest_model_input.value() == "gpt-5.4-mini"
    assert window.latest_since_input.value() == ""
    assert window.latest_home_latest_toggle.value() == 0
    assert window.run_list_column_toggles["started_at"].value() == 1
    assert window.run_list_column_toggles["status"].value() == 1
    assert window.run_list_column_toggles["digest_title"].value() == 0
    assert window.appearance_mode_choice.value() == "classic_light"
    assert window.digest_navigation_toggle.value() == 0

from __future__ import annotations

from types import ModuleType
from pathlib import Path
import sys


def _build_fake_fltk() -> ModuleType:
    module = ModuleType("fltk")
    module.FL_PUSH = 1
    module.FL_RELEASE = 2
    module.FL_RIGHT_MOUSE = 3
    module.FL_LEFT_MOUSE = 1
    module.FL_CTRL = 262144
    module.FL_SHIFT = 65536

    class Fl:
        _event_button = 0
        _event_state = 0
        _event_x_root = 0
        _event_y_root = 0

        @classmethod
        def event_button(cls) -> int:
            return cls._event_button

        @classmethod
        def event_state(cls) -> int:
            return cls._event_state

        @classmethod
        def event_x_root(cls) -> int:
            return cls._event_x_root

        @classmethod
        def event_y_root(cls) -> int:
            return cls._event_y_root

    class Fl_Multi_Browser:
        def __init__(self, x, y, width, height, label=None) -> None:  # noqa: ANN001
            self._items: list[object] = []
            self._selected_lines: set[int] = set()
            self._value = 0

        def add(self, *args) -> None:  # noqa: ANN001
            self._items.append(args)

        def size(self) -> int:
            return len(self._items)

        def value(self, selection=None):  # noqa: ANN001
            if selection is None:
                return self._value
            self._value = selection
            return self._value

        def select(self, line_number: int, flag: int) -> None:  # noqa: ANN001
            self._selected_lines.add(line_number)

        def deselect(self) -> None:
            self._selected_lines.clear()

        def selected(self, line_number: int) -> bool:
            return line_number in self._selected_lines

        def redraw(self) -> None:
            return None

        def do_callback(self) -> None:
            return None

        def handle(self, event: int) -> int:
            return 1

    class Fl_Menu_Button:
        POPUP3 = 3

        def __init__(self, x, y, width, height) -> None:  # noqa: ANN001
            self.items: list[object] = []

        def type(self, value) -> None:  # noqa: ANN001
            self.menu_type = value

        def add(self, label, shortcut, callback, data) -> None:  # noqa: ANN001
            self.items.append((label, shortcut, callback, data))

        def position(self, x: int, y: int) -> None:
            self.positioned_at = (x, y)

        def popup(self) -> None:
            return None

    module.Fl = Fl
    module.Fl_Multi_Browser = Fl_Multi_Browser
    module.Fl_Menu_Button = Fl_Menu_Button
    return module


if "fltk" not in sys.modules:
    sys.modules["fltk"] = _build_fake_fltk()

import fltk

from xs2n.ui.artifacts import RunRecord
from xs2n.ui.run_list_browser import (
    context_click_requested,
    delete_selection_message,
    fallback_run_id_after_delete,
    selected_run_indexes,
)


class FakeRunBrowser:
    def __init__(self, selected_lines: set[int]) -> None:
        self.selected_lines = selected_lines

    def selected(self, line_number: int) -> bool:
        return line_number in self.selected_lines


def test_selected_run_indexes_reads_multi_selection() -> None:
    browser = FakeRunBrowser({1, 3, 4})

    assert selected_run_indexes(browser, row_count=4) == [0, 2, 3]


def test_context_click_requested_supports_right_click_and_macos_ctrl_click() -> None:
    assert context_click_requested(
        event=1,
        event_button=3,
        event_state=0,
        platform="linux",
    ) is True
    assert context_click_requested(
        event=1,
        event_button=1,
        event_state=262144,
        platform="darwin",
    ) is True
    assert context_click_requested(
        event=1,
        event_button=1,
        event_state=262144,
        platform="linux",
    ) is False


def test_handle_plain_left_release_skips_previous_selection_snapshot(
    monkeypatch,
) -> None:
    import xs2n.ui.run_list_browser as run_list_browser

    RunListBrowser = run_list_browser.RunListBrowser

    browser = RunListBrowser(0, 0, 100, 100)
    browser.add("row-1")
    browser.add("row-2")
    browser.add("row-3")
    browser.value(2)

    snapshot_calls = 0

    def fake_selected_indexes() -> list[int]:
        nonlocal snapshot_calls
        snapshot_calls += 1
        return [0, 1]

    monkeypatch.setattr(browser, "selected_indexes", fake_selected_indexes)
    monkeypatch.setattr(browser, "_current_index", lambda: 1)
    monkeypatch.setattr(run_list_browser.fltk.Fl, "event_button", lambda: fltk.FL_LEFT_MOUSE)
    monkeypatch.setattr(run_list_browser.fltk.Fl, "event_state", lambda: 0)

    assert browser.handle(fltk.FL_RELEASE) == 1
    assert snapshot_calls == 0
    assert browser._selection_anchor_index == 1


def test_handle_ctrl_left_release_uses_previous_selection_snapshot(
    monkeypatch,
) -> None:
    import xs2n.ui.run_list_browser as run_list_browser

    RunListBrowser = run_list_browser.RunListBrowser

    browser = RunListBrowser(0, 0, 100, 100)
    browser.add("row-1")
    browser.add("row-2")
    browser.add("row-3")
    browser.select(1, 1)
    browser.select(2, 1)
    browser.value(2)

    snapshot_calls = 0
    callback_calls: list[str] = []

    def fake_selected_indexes() -> list[int]:
        nonlocal snapshot_calls
        snapshot_calls += 1
        return [0, 1, 2]

    monkeypatch.setattr(browser, "selected_indexes", fake_selected_indexes)
    monkeypatch.setattr(browser, "do_callback", lambda: callback_calls.append("called"))
    monkeypatch.setattr(browser, "_current_index", lambda: 1)
    monkeypatch.setattr(run_list_browser.fltk.Fl, "event_button", lambda: fltk.FL_LEFT_MOUSE)
    monkeypatch.setattr(
        run_list_browser.fltk.Fl,
        "event_state",
        lambda: fltk.FL_CTRL,
    )

    assert browser.handle(fltk.FL_RELEASE) == 1
    assert snapshot_calls == 1
    assert callback_calls == ["called"]


def test_fallback_run_id_after_delete_prefers_next_remaining_row() -> None:
    runs = [
        RunRecord(
            root_name="report_runs",
            run_id="20260315T203138Z",
            run_dir=Path("data/report_runs/20260315T203138Z"),
        ),
        RunRecord(
            root_name="report_runs",
            run_id="20260315T203500Z",
            run_dir=Path("data/report_runs/20260315T203500Z"),
        ),
        RunRecord(
            root_name="report_runs",
            run_id="20260315T203900Z",
            run_dir=Path("data/report_runs/20260315T203900Z"),
        ),
    ]

    assert fallback_run_id_after_delete(runs, selected_indexes=[1]) == (
        "20260315T203900Z"
    )
    assert fallback_run_id_after_delete(runs, selected_indexes=[1, 2]) == (
        "20260315T203138Z"
    )
    assert fallback_run_id_after_delete(runs, selected_indexes=[0, 1, 2]) is None


def test_delete_selection_message_mentions_count_and_path_preview() -> None:
    selected_runs = [
        RunRecord(
            root_name="report_runs",
            run_id="20260315T203138Z",
            run_dir=Path("data/report_runs/20260315T203138Z"),
        ),
        RunRecord(
            root_name="report_runs",
            run_id="20260315T203500Z",
            run_dir=Path("data/report_runs/20260315T203500Z"),
        ),
    ]

    message = delete_selection_message(selected_runs)

    assert "Delete 2 selected runs from disk?" in message
    assert "data/report_runs/20260315T203138Z" in message
    assert "data/report_runs/20260315T203500Z" in message

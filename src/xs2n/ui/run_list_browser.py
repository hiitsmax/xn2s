from __future__ import annotations

from collections.abc import Callable, Sequence
import sys

import fltk

from xs2n.ui.artifacts import RunRecord


DELETE_SELECTED_RUNS_LABEL = "Delete Selected Runs"


def context_click_requested(
    *,
    event: int,
    event_button: int,
    event_state: int,
    platform: str = sys.platform,
) -> bool:
    if event != fltk.FL_PUSH:
        return False
    if event_button == fltk.FL_RIGHT_MOUSE:
        return True
    if platform != "darwin":
        return False
    return (
        event_button == fltk.FL_LEFT_MOUSE
        and bool(event_state & fltk.FL_CTRL)
    )


def selected_run_indexes(browser, *, row_count: int) -> list[int]:  # noqa: ANN001
    return [
        index
        for index in range(row_count)
        if _browser_line_selected(browser, line_number=index + 1)
    ]


def fallback_run_id_after_delete(
    runs: Sequence[RunRecord],
    *,
    selected_indexes: Sequence[int],
) -> str | None:
    selected_index_set = {
        index
        for index in selected_indexes
        if 0 <= index < len(runs)
    }
    if not selected_index_set:
        return runs[0].run_id if runs else None

    remaining_runs = [
        run
        for index, run in enumerate(runs)
        if index not in selected_index_set
    ]
    if not remaining_runs:
        return None

    preferred_index = min(selected_index_set)
    return remaining_runs[min(preferred_index, len(remaining_runs) - 1)].run_id


def delete_selection_message(selected_runs: Sequence[RunRecord]) -> str:
    if not selected_runs:
        return "Select at least one run to delete."

    if len(selected_runs) == 1:
        run = selected_runs[0]
        return (
            f"Delete run `{run.run_id}` from disk?\n\n"
            f"This permanently removes:\n{run.run_dir}"
        )

    preview_lines = [f"- {run.run_dir}" for run in selected_runs[:3]]
    if len(selected_runs) > 3:
        preview_lines.append(f"- ... and {len(selected_runs) - 3} more")
    preview = "\n".join(preview_lines)
    return (
        f"Delete {len(selected_runs)} selected runs from disk?\n\n"
        "This permanently removes:\n"
        f"{preview}"
    )


class RunListBrowser(fltk.Fl_Multi_Browser):
    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        label: str | None = None,
        *,
        on_delete_requested: Callable[[], None] | None = None,
    ) -> None:
        if label is None:
            super().__init__(x, y, width, height)
        else:
            super().__init__(x, y, width, height, label)
        self._on_delete_requested = on_delete_requested
        self._selection_anchor_index: int | None = None
        self._suppress_context_release = False

        self._context_menu = fltk.Fl_Menu_Button(x, y, 0, 0)
        self._context_menu.type(fltk.Fl_Menu_Button.POPUP3)
        self._context_menu.add(
            DELETE_SELECTED_RUNS_LABEL,
            0,
            self._on_delete_menu_item_clicked,
            None,
        )

    def handle(self, event: int) -> int:
        if self._should_show_context_menu(event):
            self._suppress_context_release = True
            self._ensure_context_menu_selection()
            self.show_delete_context_menu()
            return 1

        if self._suppress_context_release and event == fltk.FL_RELEASE:
            self._suppress_context_release = False
            return 1

        event_state = fltk.Fl.event_state()
        shift_pressed = bool(event_state & fltk.FL_SHIFT)
        ctrl_pressed = bool(event_state & fltk.FL_CTRL)
        previous_selection: Sequence[int] = []
        if event == fltk.FL_RELEASE and (shift_pressed or ctrl_pressed):
            previous_selection = self.selected_indexes()
        handled = super().handle(event)

        if event != fltk.FL_RELEASE or fltk.Fl.event_button() != fltk.FL_LEFT_MOUSE:
            return handled

        clicked_index = self._current_index()
        if clicked_index is None:
            return handled

        if shift_pressed:
            self._apply_shift_selection(
                clicked_index=clicked_index,
                previous_selection=previous_selection,
                ctrl_pressed=ctrl_pressed,
            )
            return handled

        if ctrl_pressed:
            self._apply_ctrl_selection(
                clicked_index=clicked_index,
                previous_selection=previous_selection,
            )
            return handled

        self._selection_anchor_index = clicked_index
        return handled

    def selected_indexes(self) -> list[int]:
        return selected_run_indexes(self, row_count=self.size())

    def set_selection(
        self,
        *,
        selected_indexes: Sequence[int],
        active_index: int | None,
    ) -> None:
        self.deselect()
        for index in selected_indexes:
            if 0 <= index < self.size():
                self.select(index + 1, 1)

        if active_index is None:
            self.value(0)
            self.redraw()
            return

        if 0 <= active_index < self.size():
            self.value(active_index + 1)
        else:
            self.value(0)
        self.redraw()

    def show_delete_context_menu(self) -> None:
        self._context_menu.position(
            fltk.Fl.event_x_root(),
            fltk.Fl.event_y_root(),
        )
        self._context_menu.popup()

    def _should_show_context_menu(self, event: int) -> bool:
        return context_click_requested(
            event=event,
            event_button=fltk.Fl.event_button(),
            event_state=fltk.Fl.event_state(),
        )

    def _ensure_context_menu_selection(self) -> None:
        if self.selected_indexes():
            return
        current_index = self._current_index()
        if current_index is None:
            return
        self.set_selection(
            selected_indexes=[current_index],
            active_index=current_index,
        )

    def _apply_shift_selection(
        self,
        *,
        clicked_index: int,
        previous_selection: Sequence[int],
        ctrl_pressed: bool,
    ) -> None:
        anchor_index = self._selection_anchor_index
        if anchor_index is None:
            anchor_index = clicked_index
            self._selection_anchor_index = clicked_index

        range_indexes = list(
            range(
                min(anchor_index, clicked_index),
                max(anchor_index, clicked_index) + 1,
            )
        )
        if ctrl_pressed:
            selected_indexes = sorted(set(previous_selection) | set(range_indexes))
        else:
            selected_indexes = range_indexes

        self.set_selection(
            selected_indexes=selected_indexes,
            active_index=clicked_index,
        )

    def _apply_ctrl_selection(
        self,
        *,
        clicked_index: int,
        previous_selection: Sequence[int],
    ) -> None:
        selected_index_set = set(previous_selection)
        if clicked_index not in selected_index_set:
            selected_indexes = sorted(selected_index_set | {clicked_index})
            self.set_selection(
                selected_indexes=selected_indexes,
                active_index=clicked_index,
            )
            self._selection_anchor_index = clicked_index
            return

        selected_index_set.remove(clicked_index)
        active_index = None
        if selected_index_set:
            active_index = min(
                selected_index_set,
                key=lambda index: abs(index - clicked_index),
            )

        self.set_selection(
            selected_indexes=sorted(selected_index_set),
            active_index=active_index,
        )
        if active_index is not None:
            self.do_callback()

    def _current_index(self) -> int | None:
        current_line = self.value()
        if current_line < 1 or current_line > self.size():
            return None
        return current_line - 1

    def _on_delete_menu_item_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        if self._on_delete_requested is not None:
            self._on_delete_requested()


def _browser_line_selected(browser, *, line_number: int) -> bool:  # noqa: ANN001
    selected = getattr(browser, "selected", None)
    if callable(selected):
        return bool(selected(line_number))

    value = getattr(browser, "value", None)
    if callable(value):
        return value() == line_number

    return False

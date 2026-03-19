from __future__ import annotations

from pathlib import Path
from typing import Callable

import fltk

from xs2n.ui.digest_browser_preview import (
    render_thread_placeholder_html,
    render_thread_preview_html,
)
from xs2n.ui.digest_browser_state import DigestBrowserState
from xs2n.ui.saved_digest import load_saved_digest_preview
from xs2n.ui.theme import CLASSIC_LIGHT_THEME, UiTheme, to_fltk_color

HEADER_HEIGHT = 28
SUBTITLE_HEIGHT = 24
SUMMARY_HEIGHT = 92
TOOLBAR_HEIGHT = 32
ISSUE_LIST_WIDTH = 240
PADDING = 8

class DigestBrowser:
    def __init__(
        self,
        *,
        x: int,
        y: int,
        width: int,
        height: int,
        on_open_url: Callable[[str], None],
    ) -> None:
        self._on_open_url = on_open_url
        self._theme = CLASSIC_LIGHT_THEME
        self._state: DigestBrowserState | None = None
        self._issue_rows = []
        self._thread_rows = []
        self.group = fltk.Fl_Group(x, y, width, height)
        self.group.begin()
        self.header = fltk.Fl_Box(x, y, width, HEADER_HEIGHT, "")
        self.subtitle = fltk.Fl_Box(x, y + HEADER_HEIGHT, width, SUBTITLE_HEIGHT, "")
        self.issue_list = fltk.Fl_Hold_Browser(x, y, ISSUE_LIST_WIDTH, height)
        self.issue_summary = fltk.Fl_Box(x, y, width, SUMMARY_HEIGHT, "")
        self.open_button = fltk.Fl_Button(x, y, 96, TOOLBAR_HEIGHT, "Open on X")
        self.thread_list = fltk.Fl_Hold_Browser(x, y, width, 200)
        self.thread_preview = fltk.Fl_Help_View(x, y, width, height, "Thread Preview")
        self.group.end()
        self.group.resizable(self.thread_preview)
        self.group.hide()

        for box in (self.header, self.subtitle, self.issue_summary):
            box.align(fltk.FL_ALIGN_LEFT | fltk.FL_ALIGN_INSIDE | fltk.FL_ALIGN_WRAP)
        self.issue_list.callback(self._on_issue_selected, None)
        self.thread_list.callback(self._on_thread_selected, None)
        self.open_button.callback(self._on_open_clicked, None)
        self._layout()
        self.apply_theme(self._theme)

    def show(self) -> None:
        self.group.show()

    def hide(self) -> None:
        self.group.hide()

    def resize(self, x: int, y: int, width: int, height: int) -> None:
        self.group.resize(x, y, width, height)
        self._layout()

    def apply_theme(self, theme: UiTheme) -> None:
        self._theme = theme
        text_color = to_fltk_color(fltk, theme.text)
        self.header.box(fltk.FL_THIN_UP_BOX)
        self.header.color(to_fltk_color(fltk, theme.viewer_panel_bg))
        self.subtitle.box(fltk.FL_FLAT_BOX)
        self.subtitle.color(to_fltk_color(fltk, theme.header_bg))
        self.issue_summary.box(fltk.FL_DOWN_BOX)
        self.issue_summary.color(to_fltk_color(fltk, theme.viewer_plain_bg))
        self.thread_preview.box(fltk.FL_BORDER_BOX)
        self.thread_preview.color(to_fltk_color(fltk, theme.viewer_plain_bg))
        for widget in (
            self.header,
            self.subtitle,
            self.issue_summary,
            self.issue_list,
            self.thread_list,
            self.thread_preview,
        ):
            if hasattr(widget, "labelcolor"):
                widget.labelcolor(text_color)
            if hasattr(widget, "textcolor"):
                widget.textcolor(text_color)
        for browser in (self.issue_list, self.thread_list):
            browser.color(to_fltk_color(fltk, theme.panel_bg2))
            browser.selection_color(to_fltk_color(fltk, theme.selection_bg))
        self.open_button.color(to_fltk_color(fltk, theme.control_bg))
        self.open_button.selection_color(
            to_fltk_color(fltk, theme.control_pressed_bg)
        )
        self.open_button.labelcolor(text_color)
        self.group.redraw()

    def load_run(self, run_dir: Path) -> bool:
        preview = load_saved_digest_preview(run_dir=run_dir)
        if preview is None:
            self._state = None
            self.issue_list.clear()
            self.thread_list.clear()
            self.thread_preview.value("")
            return False
        self._state = DigestBrowserState(preview)
        self._render()
        return True

    def _layout(self) -> None:
        x = self.group.x()
        y = self.group.y()
        width = self.group.w()
        height = self.group.h()
        right_x = x + ISSUE_LIST_WIDTH + PADDING
        right_width = max(1, width - ISSUE_LIST_WIDTH - PADDING)
        thread_list_y = y + HEADER_HEIGHT + SUBTITLE_HEIGHT + SUMMARY_HEIGHT + TOOLBAR_HEIGHT + (PADDING * 2)
        preview_y = thread_list_y + 184 + PADDING
        preview_height = max(1, height - (preview_y - y))
        self.header.resize(x, y, width, HEADER_HEIGHT)
        self.subtitle.resize(x, y + HEADER_HEIGHT, width, SUBTITLE_HEIGHT)
        self.issue_list.resize(x, y + HEADER_HEIGHT + SUBTITLE_HEIGHT, ISSUE_LIST_WIDTH, height - HEADER_HEIGHT - SUBTITLE_HEIGHT)
        self.issue_summary.resize(right_x, y + HEADER_HEIGHT + SUBTITLE_HEIGHT, right_width, SUMMARY_HEIGHT)
        self.open_button.resize(right_x, y + HEADER_HEIGHT + SUBTITLE_HEIGHT + SUMMARY_HEIGHT + PADDING, 96, TOOLBAR_HEIGHT)
        self.thread_list.resize(right_x, thread_list_y, right_width, 184)
        self.thread_preview.resize(right_x, preview_y, right_width, preview_height)

    def _render(self) -> None:
        if self._state is None:
            return
        self.header.label(f" {self._state.digest_title}")
        self.subtitle.label(f" {self._state.run_summary}")
        self._issue_rows = self._state.issue_rows()
        self.issue_list.clear()
        for issue in self._issue_rows:
            self.issue_list.add(f"{issue.title} ({issue.thread_count})")
        selected_issue = self._state.selected_issue()
        selected_index = next(
            (index for index, issue in enumerate(self._issue_rows) if issue.slug == selected_issue.slug),
            0,
        )
        self.issue_list.value(selected_index + 1)
        self.issue_summary.label(f" {selected_issue.title}\n\n{selected_issue.summary}")
        self._thread_rows = self._state.thread_rows()
        self.thread_list.clear()
        for row in self._thread_rows:
            self.thread_list.add(f"{row.title} | {row.summary}")
        preview = self._state.thread_preview()
        if preview is None:
            self.thread_preview.value(
                render_thread_placeholder_html(
                    issue_title=selected_issue.title,
                    theme=self._theme,
                )
            )
            self.open_button.deactivate()
        else:
            selected_thread = self._state.selected_thread()
            selected_thread_index = next(
                (
                    index
                    for index, row in enumerate(self._thread_rows)
                    if selected_thread is not None
                    and row.thread_id == selected_thread.thread_id
                ),
                0,
            )
            self.thread_list.value(selected_thread_index + 1)
            self.thread_preview.value(render_thread_preview_html(preview, self._theme))
            self.open_button.activate()
        self.group.redraw()

    def _on_issue_selected(self, widget, data=None) -> None:  # noqa: ANN001
        if self._state is None:
            return
        selection = widget.value()
        if selection < 1 or selection > len(self._issue_rows):
            return
        self._state.select_issue(self._issue_rows[selection - 1].slug)
        self._render()

    def _on_thread_selected(self, widget, data=None) -> None:  # noqa: ANN001
        if self._state is None:
            return
        selection = widget.value()
        if selection < 1 or selection > len(self._thread_rows):
            return
        self._state.select_thread(self._thread_rows[selection - 1].thread_id)
        self._render()

    def _on_open_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        if self._state is None:
            return
        preview = self._state.thread_preview()
        if preview is not None:
            self._on_open_url(preview.open_url)

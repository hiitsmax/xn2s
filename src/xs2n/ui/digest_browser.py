from __future__ import annotations

from pathlib import Path
from typing import Callable

import fltk

from xs2n.ui.digest_browser_state import DigestBrowserRow, DigestBrowserState
from xs2n.ui.saved_digest import load_saved_digest_preview
from xs2n.ui.theme import CLASSIC_LIGHT_THEME, UiTheme, to_fltk_color


HEADER_HEIGHT = 28
SUBTITLE_HEIGHT = 28
TOOLBAR_HEIGHT = 34
SUMMARY_HEIGHT = 118
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
        self._rows: list[DigestBrowserRow] = []

        self.group = fltk.Fl_Group(x, y, width, height)
        self.group.begin()
        self.header = fltk.Fl_Box(x, y, width, HEADER_HEIGHT, "")
        self.subtitle = fltk.Fl_Box(x, y + HEADER_HEIGHT, width, SUBTITLE_HEIGHT, "")
        self.back_button = fltk.Fl_Button(x, y, 72, TOOLBAR_HEIGHT, "@<- Back")
        self.open_button = fltk.Fl_Button(x + 76, y, 96, TOOLBAR_HEIGHT, "Open on X")
        self.summary = fltk.Fl_Box(x, y, width, SUMMARY_HEIGHT, "")
        self.content = fltk.Fl_Hold_Browser(x, y, width, height)
        self.group.end()
        self.group.resizable(self.content)
        self.group.hide()

        self.summary.align(
            fltk.FL_ALIGN_LEFT | fltk.FL_ALIGN_INSIDE | fltk.FL_ALIGN_WRAP
        )
        self.subtitle.align(
            fltk.FL_ALIGN_LEFT | fltk.FL_ALIGN_INSIDE | fltk.FL_ALIGN_CLIP
        )
        self.header.align(
            fltk.FL_ALIGN_LEFT | fltk.FL_ALIGN_INSIDE | fltk.FL_ALIGN_CLIP
        )
        self.back_button.callback(self._on_back_clicked, None)
        self.open_button.callback(self._on_open_clicked, None)
        self.content.callback(self._on_content_selected, None)
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
        self.header.labelcolor(text_color)
        self.subtitle.box(fltk.FL_FLAT_BOX)
        self.subtitle.color(to_fltk_color(fltk, theme.header_bg))
        self.subtitle.labelcolor(text_color)
        self.summary.box(fltk.FL_DOWN_BOX)
        self.summary.color(to_fltk_color(fltk, theme.viewer_plain_bg))
        self.summary.labelcolor(text_color)
        for button in (self.back_button, self.open_button):
            button.color(to_fltk_color(fltk, theme.control_bg))
            button.selection_color(to_fltk_color(fltk, theme.control_pressed_bg))
            button.labelcolor(text_color)
        self.content.color(to_fltk_color(fltk, theme.panel_bg2))
        self.content.selection_color(to_fltk_color(fltk, theme.selection_bg))
        self.content.textcolor(text_color)
        self.content.labelcolor(text_color)
        self.group.redraw()

    def load_run(self, run_dir: Path) -> bool:
        preview = load_saved_digest_preview(run_dir=run_dir)
        if preview is None:
            self._state = None
            self._rows = []
            self.content.clear()
            return False
        self._state = DigestBrowserState(preview)
        self.show_overview()
        return True

    def show_overview(self) -> None:
        if self._state is None:
            return
        self._state.show_overview()
        self._render()

    def show_thread(self, thread_id: str) -> None:
        if self._state is None:
            return
        self._state.show_thread(thread_id)
        self._render()

    def go_back(self) -> None:
        if self._state is None:
            return
        self._state.go_back()
        self._render()

    def _layout(self) -> None:
        x = self.group.x()
        y = self.group.y()
        width = self.group.w()
        height = self.group.h()
        toolbar_y = y + HEADER_HEIGHT + SUBTITLE_HEIGHT
        summary_y = toolbar_y + TOOLBAR_HEIGHT + PADDING
        content_y = summary_y + SUMMARY_HEIGHT + PADDING
        content_height = max(1, height - (content_y - y))
        self.header.resize(x, y, width, HEADER_HEIGHT)
        self.subtitle.resize(x, y + HEADER_HEIGHT, width, SUBTITLE_HEIGHT)
        self.back_button.resize(x, toolbar_y, 72, TOOLBAR_HEIGHT)
        self.open_button.resize(x + 76, toolbar_y, 96, TOOLBAR_HEIGHT)
        self.summary.resize(x, summary_y, width, SUMMARY_HEIGHT)
        self.content.resize(x, content_y, width, content_height)

    def _render(self) -> None:
        if self._state is None:
            return
        screen = self._state.current_screen()
        self.header.label(f" {screen.title}")
        self.subtitle.label(f" {screen.subtitle}")
        self.summary.label(f" {screen.summary}")
        self._rows = screen.rows
        self.content.clear()
        for row in self._rows:
            self.content.add(row.label)
        if screen.can_go_back:
            self.back_button.activate()
        else:
            self.back_button.deactivate()
        if screen.open_url:
            self.open_button.activate()
        else:
            self.open_button.deactivate()
        self.group.redraw()

    def _on_content_selected(self, widget, data=None) -> None:  # noqa: ANN001
        if self._state is None:
            return
        selection = widget.value()
        if selection < 1 or selection > len(self._rows):
            return
        row = self._rows[selection - 1]
        if row.kind == "thread" and row.thread_id is not None:
            self.show_thread(row.thread_id)

    def _on_back_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        self.go_back()

    def _on_open_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        if self._state is None:
            return
        screen = self._state.current_screen()
        if screen.open_url:
            self._on_open_url(screen.open_url)

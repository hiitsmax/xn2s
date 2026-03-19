from __future__ import annotations

from pathlib import Path
from typing import Callable

import fltk

from xs2n.ui.digest_browser_preview import (
    render_issue_canvas_text,
    render_issue_placeholder_text,
)
from xs2n.ui.digest_browser_state import DigestBrowserState
from xs2n.ui.saved_digest import load_saved_digest_preview
from xs2n.ui.theme import CLASSIC_LIGHT_THEME, UiTheme, to_fltk_color

HEADER_HEIGHT = 28
SUBTITLE_HEIGHT = 24
SUMMARY_HEIGHT = 126
TOOLBAR_HEIGHT = 30
ISSUE_LIST_WIDTH = 320
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
        self.group = fltk.Fl_Group(x, y, width, height)
        self.group.begin()
        self.header = fltk.Fl_Box(x, y, width, HEADER_HEIGHT, "")
        self.subtitle = fltk.Fl_Box(x, y + HEADER_HEIGHT, width, SUBTITLE_HEIGHT, "")
        self.issue_list = fltk.Fl_Hold_Browser(x, y, ISSUE_LIST_WIDTH, height)
        self.issue_summary = fltk.Fl_Box(x, y, width, SUMMARY_HEIGHT, "")
        self.open_button = fltk.Fl_Button(x, y, 132, TOOLBAR_HEIGHT, "Open lead thread")
        self.issue_canvas = fltk.Fl_Text_Display(x, y, width, height)
        self.issue_canvas_buffer = fltk.Fl_Text_Buffer()
        self.issue_canvas.buffer(self.issue_canvas_buffer)
        self.group.end()
        self.group.resizable(self.issue_canvas)
        self.group.hide()

        for box in (self.header, self.subtitle, self.issue_summary):
            box.align(fltk.FL_ALIGN_LEFT | fltk.FL_ALIGN_INSIDE | fltk.FL_ALIGN_WRAP)
        self.issue_list.callback(self._on_issue_selected, None)
        self.open_button.callback(self._on_open_clicked, None)
        if hasattr(self.issue_list, "column_char"):
            self.issue_list.column_char("\t")
        if hasattr(self.open_button, "tooltip"):
            self.open_button.tooltip(
                "Open the lead thread for the selected issue on X."
            )
        if hasattr(self.issue_canvas, "wrap_mode"):
            self.issue_canvas.wrap_mode(
                fltk.Fl_Text_Display.WRAP_AT_BOUNDS,
                0,
            )
        if hasattr(self.issue_canvas, "linenumber_width"):
            self.issue_canvas.linenumber_width(0)
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
        self.issue_canvas.box(fltk.FL_BORDER_BOX)
        self.issue_canvas.color(to_fltk_color(fltk, theme.viewer_bg))
        if hasattr(self.issue_canvas, "textcolor"):
            self.issue_canvas.textcolor(text_color)
        if hasattr(self.issue_canvas, "textsize"):
            self.issue_canvas.textsize(14)
        if hasattr(self.issue_canvas, "textfont"):
            self.issue_canvas.textfont(fltk.FL_COURIER)
        for widget in (
            self.header,
            self.subtitle,
            self.issue_summary,
            self.issue_list,
        ):
            if hasattr(widget, "labelcolor"):
                widget.labelcolor(text_color)
            if hasattr(widget, "textcolor"):
                widget.textcolor(text_color)
        if hasattr(self.issue_summary, "labelsize"):
            self.issue_summary.labelsize(13)
        self.issue_list.color(to_fltk_color(fltk, theme.panel_bg2))
        self.issue_list.selection_color(to_fltk_color(fltk, theme.selection_bg))
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
            self.issue_canvas_buffer.text("")
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
        summary_y = y + HEADER_HEIGHT + SUBTITLE_HEIGHT
        button_y = summary_y + SUMMARY_HEIGHT + PADDING
        canvas_y = button_y + TOOLBAR_HEIGHT + PADDING
        canvas_height = max(1, height - (canvas_y - y))

        self.header.resize(x, y, width, HEADER_HEIGHT)
        self.subtitle.resize(x, y + HEADER_HEIGHT, width, SUBTITLE_HEIGHT)
        self.issue_list.resize(
            x,
            y + HEADER_HEIGHT + SUBTITLE_HEIGHT,
            ISSUE_LIST_WIDTH,
            height - HEADER_HEIGHT - SUBTITLE_HEIGHT,
        )
        self.issue_summary.resize(right_x, summary_y, right_width, SUMMARY_HEIGHT)
        self.open_button.resize(right_x, button_y, 132, TOOLBAR_HEIGHT)
        self.issue_canvas.resize(right_x, canvas_y, right_width, canvas_height)
        self._configure_issue_list_columns()

    def _render(self) -> None:
        if self._state is None:
            return

        self.header.label(f" {self._state.digest_title}")
        self.subtitle.label(f" {self._state.run_summary}")
        self._issue_rows = self._state.issue_rows()
        self.issue_list.clear()
        for issue_row in self._issue_rows:
            self.issue_list.add(_format_issue_row_label(issue_row))

        selected_issue = self._state.selected_issue()
        selected_index = next(
            (
                index
                for index, issue_row in enumerate(self._issue_rows)
                if issue_row.slug == selected_issue.slug
            ),
            0,
        )
        self.issue_list.value(selected_index + 1)

        issue_preview = self._state.selected_issue_preview()
        if issue_preview is None:
            self.issue_summary.label(" No issue selected")
            self.issue_canvas_buffer.text(
                render_issue_placeholder_text(
                    issue_title="Selected issue",
                )
            )
            self.open_button.deactivate()
        else:
            self.issue_summary.label(_format_issue_summary_label(issue_preview))
            self.issue_canvas_buffer.text(
                render_issue_canvas_text(issue_preview)
            )
            self.issue_canvas.insert_position(0)
            self.issue_canvas.show_insert_position()
            if issue_preview.lead_open_url:
                self.open_button.activate()
            else:
                self.open_button.deactivate()
        self.group.redraw()

    def _configure_issue_list_columns(self) -> None:
        if not hasattr(self.issue_list, "column_widths"):
            return

        list_width = self.issue_list.w()
        rank_width = 34
        priority_width = 54
        density_width = 66
        title_width = max(1, list_width - rank_width - priority_width - density_width - 18)
        self.issue_list.column_widths(
            (
                rank_width,
                priority_width,
                density_width,
                title_width,
                0,
            )
        )

    def _on_issue_selected(self, widget, data=None) -> None:  # noqa: ANN001
        if self._state is None:
            return
        selection = widget.value()
        if selection < 1 or selection > len(self._issue_rows):
            return
        self._state.select_issue(self._issue_rows[selection - 1].slug)
        self._render()

    def _on_open_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        if self._state is None:
            return
        issue_preview = self._state.selected_issue_preview()
        if issue_preview is not None and issue_preview.lead_open_url:
            self._on_open_url(issue_preview.lead_open_url)


def _format_issue_row_label(issue_row) -> str:  # noqa: ANN001
    density = f"{issue_row.thread_count}T/{issue_row.tweet_count}P"
    title = _truncate_text(issue_row.title, limit=38)
    return (
        f"{issue_row.rank:02d}\t"
        f"{issue_row.priority_label}\t"
        f"{density}\t"
        f"{title}"
    )


def _format_issue_summary_label(issue_preview) -> str:  # noqa: ANN001
    latest_label = (
        issue_preview.latest_created_at.strftime("%Y-%m-%d %H:%M UTC")
        if issue_preview.latest_created_at is not None
        else "n/a"
    )
    return (
        f" {issue_preview.issue_title}\n"
        f" Priority #{issue_preview.priority_rank:02d} | "
        f"{issue_preview.priority_label} | "
        f"{issue_preview.thread_count} threads | "
        f"{issue_preview.tweet_count} posts\n"
        f" Latest signal: {latest_label}\n\n"
        f"{issue_preview.issue_summary}"
    )


def _truncate_text(value: str, *, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: max(0, limit - 3)].rstrip()}..."

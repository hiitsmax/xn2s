from __future__ import annotations

from pathlib import Path
from typing import Callable

import fltk

from xs2n.ui.digest_browser_cards import (
    CARD_LIST_GAP,
    CARD_LIST_PADDING,
    build_digest_empty_state,
    build_digest_thread_card,
    hide_digest_thread_card,
    update_digest_thread_card,
)
from xs2n.ui.digest_browser_preview import (
    build_issue_summary_panel,
)
from xs2n.ui.digest_browser_state import DigestBrowserState
from xs2n.ui.saved_digest import load_saved_digest_preview
from xs2n.ui.theme import CLASSIC_LIGHT_THEME, UiTheme, to_fltk_color

HEADER_HEIGHT = 28
SUBTITLE_HEIGHT = 24
ISSUE_HEADER_HEIGHT = 24
SUMMARY_HEIGHT = 154
TOOLBAR_HEIGHT = 30
ISSUE_LIST_WIDTH_RATIO = 0.27
ISSUE_LIST_WIDTH_MIN = 240
ISSUE_LIST_WIDTH_MAX = 420
ISSUE_THREAD_COUNT_WIDTH = 68
PADDING = 8
SUMMARY_SURFACE_PADDING_X = 14
SUMMARY_SURFACE_PADDING_Y = 10
SUMMARY_VERTICAL_GAP = 6
SUMMARY_TITLE_HEIGHT = 28
SUMMARY_META_HEIGHT = 18
RIGHT_COLUMN_INSET = 10


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
        issue_list_width = _issue_list_width(width)
        self.issue_title_header = fltk.Fl_Button(x, y, issue_list_width, ISSUE_HEADER_HEIGHT, "")
        self.issue_thread_count_header = fltk.Fl_Button(x, y, ISSUE_THREAD_COUNT_WIDTH, ISSUE_HEADER_HEIGHT, "")
        self.issue_list = fltk.Fl_Hold_Browser(x, y, issue_list_width, height)
        self.issue_summary_surface = fltk.Fl_Box(x, y, width, SUMMARY_HEIGHT, "")
        self.issue_title = fltk.Fl_Box(x, y, width, SUMMARY_TITLE_HEIGHT, "")
        self.issue_meta = fltk.Fl_Box(x, y, width, SUMMARY_META_HEIGHT, "")
        self.issue_blurb = fltk.Fl_Box(x, y, width, SUMMARY_HEIGHT - SUMMARY_TITLE_HEIGHT - SUMMARY_META_HEIGHT, "")
        self.open_button = fltk.Fl_Button(x, y, 132, TOOLBAR_HEIGHT, "Open lead thread")
        self.issue_thread_scroll = fltk.Fl_Scroll(x, y, width, height)
        self._issue_thread_cards = []
        self._issue_thread_empty_state = None
        self.group.end()
        self.group.resizable(self.issue_thread_scroll)
        self.group.hide()

        for box in (
            self.header,
            self.subtitle,
            self.issue_title,
            self.issue_meta,
            self.issue_blurb,
        ):
            box.align(fltk.FL_ALIGN_LEFT | fltk.FL_ALIGN_INSIDE | fltk.FL_ALIGN_WRAP)
        self.issue_title_header.align(fltk.FL_ALIGN_LEFT | fltk.FL_ALIGN_INSIDE)
        self.issue_thread_count_header.align(fltk.FL_ALIGN_CENTER | fltk.FL_ALIGN_INSIDE)
        self.issue_list.callback(self._on_issue_selected, None)
        self.issue_title_header.callback(self._on_title_sort_clicked, None)
        self.issue_thread_count_header.callback(self._on_thread_count_sort_clicked, None)
        self.open_button.callback(self._on_open_clicked, None)
        if hasattr(self.issue_list, "column_char"):
            self.issue_list.column_char("\t")
        if hasattr(self.open_button, "tooltip"):
            self.open_button.tooltip(
                "Open the lead thread for the selected issue on X."
            )
        self._layout()
        self.apply_theme(self._theme)
        self._render_issue_sort_headers()

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
        self.issue_summary_surface.box(fltk.FL_DOWN_BOX)
        self.issue_summary_surface.color(to_fltk_color(fltk, theme.viewer_plain_bg))
        for header_button in (
            self.issue_title_header,
            self.issue_thread_count_header,
        ):
            header_button.box(fltk.FL_THIN_UP_BOX)
            header_button.color(to_fltk_color(fltk, theme.header_cell_bg))
            header_button.selection_color(
                to_fltk_color(fltk, theme.control_pressed_bg)
            )
            header_button.labelcolor(text_color)
            if hasattr(header_button, "labelsize"):
                header_button.labelsize(12)
            if hasattr(header_button, "labelfont"):
                header_button.labelfont(fltk.FL_HELVETICA_BOLD)
        self.issue_title.box(fltk.FL_FLAT_BOX)
        self.issue_title.color(to_fltk_color(fltk, theme.viewer_plain_bg))
        self.issue_meta.box(fltk.FL_FLAT_BOX)
        self.issue_meta.color(to_fltk_color(fltk, theme.viewer_plain_bg))
        self.issue_blurb.box(fltk.FL_FLAT_BOX)
        self.issue_blurb.color(to_fltk_color(fltk, theme.viewer_plain_bg))
        self.issue_thread_scroll.box(fltk.FL_DOWN_BOX)
        self.issue_thread_scroll.color(to_fltk_color(fltk, theme.viewer_bg))
        if hasattr(self.issue_thread_scroll, "scrollbar_size"):
            self.issue_thread_scroll.scrollbar_size(14)
        for widget in (
            self.header,
            self.subtitle,
            self.issue_title,
            self.issue_meta,
            self.issue_blurb,
            self.issue_list,
            self.issue_title_header,
            self.issue_thread_count_header,
        ):
            if hasattr(widget, "labelcolor"):
                widget.labelcolor(text_color)
            if hasattr(widget, "textcolor"):
                widget.textcolor(text_color)
        if hasattr(self.issue_title, "labelsize"):
            self.issue_title.labelsize(21)
        if hasattr(self.issue_title, "labelfont"):
            self.issue_title.labelfont(fltk.FL_HELVETICA_BOLD)
        if hasattr(self.issue_meta, "labelsize"):
            self.issue_meta.labelsize(12)
        if hasattr(self.issue_meta, "labelcolor"):
            self.issue_meta.labelcolor(to_fltk_color(fltk, theme.muted_text))
        if hasattr(self.issue_blurb, "labelsize"):
            self.issue_blurb.labelsize(14)
        if hasattr(self.issue_blurb, "labelfont"):
            self.issue_blurb.labelfont(fltk.FL_HELVETICA)
        self.issue_list.color(to_fltk_color(fltk, theme.panel_bg2))
        self.issue_list.selection_color(to_fltk_color(fltk, theme.selection_bg))
        if hasattr(self.issue_list, "textsize"):
            self.issue_list.textsize(15)
        self.open_button.color(to_fltk_color(fltk, theme.control_bg))
        self.open_button.selection_color(
            to_fltk_color(fltk, theme.control_pressed_bg)
        )
        self.open_button.labelcolor(text_color)
        if hasattr(self.open_button, "labelsize"):
            self.open_button.labelsize(12)
        if (
            self._state is not None
            or self._issue_thread_cards
            or self._issue_thread_empty_state is not None
        ):
            self._render_thread_cards()
        self.group.redraw()

    def load_run(self, run_dir: Path) -> bool:
        preview = load_saved_digest_preview(run_dir=run_dir)
        if preview is None:
            self._state = None
            self.issue_list.clear()
            self._clear_thread_cards()
            return False
        self._state = DigestBrowserState(preview)
        self._render()
        return True

    def _layout(self) -> None:
        x = self.group.x()
        y = self.group.y()
        width = self.group.w()
        height = self.group.h()
        issue_list_width = _issue_list_width(width)
        right_x = x + issue_list_width + PADDING + RIGHT_COLUMN_INSET
        right_width = max(1, width - issue_list_width - (PADDING * 2) - RIGHT_COLUMN_INSET)
        issue_header_y = y + HEADER_HEIGHT + SUBTITLE_HEIGHT
        summary_y = issue_header_y
        button_y = summary_y + SUMMARY_HEIGHT + PADDING
        canvas_y = button_y + TOOLBAR_HEIGHT + PADDING
        canvas_height = max(1, height - (canvas_y - y))
        summary_inner_x = right_x + SUMMARY_SURFACE_PADDING_X
        summary_inner_y = summary_y + SUMMARY_SURFACE_PADDING_Y
        summary_inner_width = max(1, right_width - (SUMMARY_SURFACE_PADDING_X * 2))
        meta_y = summary_inner_y + SUMMARY_TITLE_HEIGHT + SUMMARY_VERTICAL_GAP
        blurb_y = meta_y + SUMMARY_META_HEIGHT + SUMMARY_VERTICAL_GAP
        blurb_height = max(
            1,
            (summary_y + SUMMARY_HEIGHT - SUMMARY_SURFACE_PADDING_Y) - blurb_y,
        )

        self.header.resize(x, y, width, HEADER_HEIGHT)
        self.subtitle.resize(x, y + HEADER_HEIGHT, width, SUBTITLE_HEIGHT)
        title_header_width, thread_count_header_width = self._issue_header_widths(
            issue_list_width
        )
        self.issue_title_header.resize(
            x,
            issue_header_y,
            title_header_width,
            ISSUE_HEADER_HEIGHT,
        )
        self.issue_thread_count_header.resize(
            x + title_header_width,
            issue_header_y,
            thread_count_header_width,
            ISSUE_HEADER_HEIGHT,
        )
        self.issue_list.resize(
            x,
            issue_header_y + ISSUE_HEADER_HEIGHT,
            issue_list_width,
            height - HEADER_HEIGHT - SUBTITLE_HEIGHT - ISSUE_HEADER_HEIGHT,
        )
        self.issue_summary_surface.resize(right_x, summary_y, right_width, SUMMARY_HEIGHT)
        self.issue_title.resize(
            summary_inner_x,
            summary_inner_y,
            summary_inner_width,
            SUMMARY_TITLE_HEIGHT,
        )
        self.issue_meta.resize(
            summary_inner_x,
            meta_y,
            summary_inner_width,
            SUMMARY_META_HEIGHT,
        )
        self.issue_blurb.resize(
            summary_inner_x,
            blurb_y,
            summary_inner_width,
            blurb_height,
        )
        self.open_button.resize(summary_inner_x, button_y, 132, TOOLBAR_HEIGHT)
        self.issue_thread_scroll.resize(right_x, canvas_y, right_width, canvas_height)
        self._configure_issue_list_columns()
        if (
            self._state is not None
            or self._issue_thread_cards
            or self._issue_thread_empty_state is not None
        ):
            self._render_thread_cards()

    def _render(self) -> None:
        if self._state is None:
            return

        self.header.label(f" {self._state.digest_title}")
        self.subtitle.label(f" {self._state.run_summary}")
        self._render_issue_sort_headers()
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
            panel = build_issue_summary_panel(issue_preview)
            self.issue_title.label(panel.title)
            self.issue_meta.label("")
            self.issue_blurb.label(panel.blurb)
            self._render_thread_cards()
            self.open_button.deactivate()
        else:
            panel = build_issue_summary_panel(issue_preview)
            self.issue_title.label(panel.title)
            self.issue_meta.label(panel.meta)
            self.issue_blurb.label(panel.blurb)
            self._render_thread_cards()
            if issue_preview.lead_open_url:
                self.open_button.activate()
            else:
                self.open_button.deactivate()
        self.group.redraw()

    def _render_thread_cards(self) -> None:
        issue_preview = (
            None if self._state is None else self._state.selected_issue_preview()
        )
        scroll_x = self.issue_thread_scroll.x()
        scroll_y = self.issue_thread_scroll.y()
        scroll_width = self.issue_thread_scroll.w()
        card_x = scroll_x + CARD_LIST_PADDING
        card_y = scroll_y + CARD_LIST_PADDING
        card_width = max(1, scroll_width - (CARD_LIST_PADDING * 2) - 16)

        if issue_preview is None or not issue_preview.threads:
            self._hide_all_thread_cards()
            if self._issue_thread_empty_state is None:
                self._issue_thread_empty_state = build_digest_empty_state(
                    parent=self.issue_thread_scroll,
                    x=card_x,
                    y=card_y,
                    width=card_width,
                    message="Issue overview will appear here as soon as the selected issue has thread data.",
                    theme=self._theme,
                )
            else:
                self._issue_thread_empty_state.resize(card_x, card_y, card_width, 72)
                self._issue_thread_empty_state.show()
            self.issue_thread_scroll.init_sizes()
            return

        if self._issue_thread_empty_state is not None:
            self._issue_thread_empty_state.hide()

        for thread_index, thread_card in enumerate(issue_preview.threads, start=1):
            if thread_index > len(self._issue_thread_cards):
                self._issue_thread_cards.append(
                    build_digest_thread_card(
                        parent=self.issue_thread_scroll,
                        x=card_x,
                        y=card_y,
                        width=card_width,
                        thread_index=thread_index,
                        thread_card=thread_card,
                        theme=self._theme,
                    )
                )
            else:
                update_digest_thread_card(
                    widgets=self._issue_thread_cards[thread_index - 1],
                    x=card_x,
                    y=card_y,
                    width=card_width,
                    thread_index=thread_index,
                    thread_card=thread_card,
                    theme=self._theme,
                )
            card_y += self._issue_thread_cards[thread_index - 1].group.h() + CARD_LIST_GAP
        for widgets in self._issue_thread_cards[len(issue_preview.threads):]:
            hide_digest_thread_card(widgets)
        self.issue_thread_scroll.init_sizes()
        self.issue_thread_scroll.scroll_to(0, 0)

    def _clear_thread_cards(self) -> None:
        self._hide_all_thread_cards()
        if self._issue_thread_empty_state is not None:
            self._issue_thread_empty_state.hide()

    def _hide_all_thread_cards(self) -> None:
        for widgets in self._issue_thread_cards:
            hide_digest_thread_card(widgets)

    def _configure_issue_list_columns(self) -> None:
        if not hasattr(self.issue_list, "column_widths"):
            return

        list_width = self.issue_list.w()
        _title_header_width, thread_count_width = self._issue_header_widths()
        title_width = max(1, list_width - thread_count_width - 18)
        self.issue_list.column_widths(
            (
                title_width,
                thread_count_width,
                0,
            )
        )

    def _issue_header_widths(
        self,
        issue_list_width: int | None = None,
    ) -> tuple[int, int]:
        if issue_list_width is None:
            issue_list_width = self.issue_list.w()
        thread_count_width = ISSUE_THREAD_COUNT_WIDTH
        title_width = max(1, issue_list_width - thread_count_width)
        return title_width, thread_count_width

    def _render_issue_sort_headers(self) -> None:
        sort_key = "thread_count"
        ascending = False
        if self._state is not None:
            sort_state = self._state.issue_sort()
            sort_key = sort_state.key
            ascending = sort_state.ascending

        self.issue_title_header.label(
            _format_sort_header_label(
                "Title",
                active=sort_key == "title",
                ascending=ascending,
            )
        )
        self.issue_thread_count_header.label(
            _format_sort_header_label(
                "Threads",
                active=sort_key == "thread_count",
                ascending=ascending,
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

    def _on_title_sort_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        if self._state is None:
            return
        self._state.toggle_issue_sort("title")
        self._render()

    def _on_thread_count_sort_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        if self._state is None:
            return
        self._state.toggle_issue_sort("thread_count")
        self._render()


def _format_issue_row_label(issue_row) -> str:  # noqa: ANN001
    return issue_row.render_label()


def _format_sort_header_label(
    label: str,
    *,
    active: bool,
    ascending: bool,
) -> str:
    if not active:
        return label
    arrow = "^" if ascending else "v"
    return f"{label} {arrow}"


def _issue_list_width(total_width: int) -> int:
    proportional_width = int(total_width * ISSUE_LIST_WIDTH_RATIO)
    return max(
        ISSUE_LIST_WIDTH_MIN,
        min(ISSUE_LIST_WIDTH_MAX, proportional_width),
    )

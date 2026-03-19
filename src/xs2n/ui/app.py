from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
import signal
import subprocess
import sys
import threading
import webbrowser

import fltk

from xs2n.schemas.auth import AuthDoctorResult, ProviderStatus, RunReadiness
from xs2n.storage.ui_state import DEFAULT_UI_STATE_PATH, load_ui_state, save_ui_state
from xs2n.ui.artifacts import (
    DEFAULT_UI_DATA_PATH,
    ArtifactRecord,
    ArtifactSectionRecord,
    RunRecord,
    delete_runs,
    list_artifact_sections,
    list_run_artifacts,
    scan_runs,
)
from xs2n.ui.auth_commands import (
    build_auth_doctor_command,
    build_codex_login_command,
    build_codex_logout_command,
    build_x_login_command,
    build_x_reset_command,
)
from xs2n.ui.auth_window import AuthWindow
from xs2n.ui.fonts import apply_default_ui_font_defaults
from xs2n.ui.macos import APP_NAME, apply_macos_app_menu, prepare_macos_app_menu
from xs2n.ui.saved_digest import find_saved_issue_thread, load_saved_digest_preview
from xs2n.ui.run_list import (
    RUN_LIST_COLUMNS,
    compute_run_list_widths,
    format_run_list_row,
    visible_run_list_columns,
)
from xs2n.ui.run_list_browser import (
    RunListBrowser,
    delete_selection_message,
    fallback_run_id_after_delete,
    selected_run_indexes,
)
from xs2n.ui.run_arguments import RunCommand
from xs2n.ui.run_preferences import RunPreferencesWindow
from xs2n.ui.source_preview import (
    INTERNAL_DIGEST_URI,
    parse_thread_source_uri,
    render_saved_thread_source_html,
)
from xs2n.ui.theme import (
    CLASSIC_LIGHT_THEME,
    UiTheme,
    apply_fltk_theme_defaults,
    normalize_appearance_mode,
    resolve_ui_theme,
    to_fltk_color,
)
from xs2n.ui.viewer import (
    render_artifact_html,
    render_loading_artifact_html,
    render_plain_text_html,
)


WINDOW_WIDTH = 1480
WINDOW_HEIGHT = 920
MENU_HEIGHT = 32
COMMAND_HEIGHT = 36
STATUS_HEIGHT = 24
LEFT_PANE_WIDTH = 380
MIDDLE_PANE_WIDTH = 340
NAVIGATION_HEADER_HEIGHT = 26
NAVIGATION_PANE_GAP = 8
SECTIONS_BROWSER_HEIGHT = 188
RUN_LIST_HEADER_HEIGHT = 26
COMMAND_STRIP_PADDING = 8
COMMAND_BUTTON_WIDTH = 30
COMMAND_BUTTON_HEIGHT = 24
COMMAND_BUTTON_GAP = 6
FOCUS_BUTTON_SYMBOL = "@search"
VIEWER_MIN_WIDTH = 220
PRIMARY_RUN_BUTTON_SYMBOL = "@>"
PRIMARY_RUN_BUTTON_TOOLTIP = "Run the configured `xs2n report latest` command."
RUN_MENU_LAUNCH_LABELS = (
    "&Run/&Refresh Following Sources",
    "&Run/&Latest 24h",
)

COMMAND_STRIP_COLOR = fltk.fl_rgb_color(212, 208, 200)
COMMAND_BUTTON_COLOR = fltk.fl_rgb_color(212, 208, 200)
COMMAND_BUTTON_PRESSED_COLOR = fltk.fl_rgb_color(181, 181, 174)
COMMAND_TEXT_COLOR = fltk.fl_rgb_color(32, 32, 32)
RUN_LIST_HEADER_COLOR = fltk.fl_rgb_color(208, 204, 194)
RUN_LIST_HEADER_CELL_COLOR = fltk.fl_rgb_color(223, 220, 213)
TOOLTIP_COLOR = fltk.fl_rgb_color(255, 255, 225)
MENU_LABEL_SIZE = 14
MENU_TEXT_SIZE = 15


def _run_browser_event_loop(*, close_browser: Callable[[], None]) -> None:
    close_requested = False
    previous_sigint_handler = signal.getsignal(signal.SIGINT)

    def request_close(_signum, _frame) -> None:  # noqa: ANN001
        nonlocal close_requested
        close_requested = True

    def close_on_idle(_data=None) -> None:  # noqa: ANN001
        nonlocal close_requested
        if not close_requested:
            return

        close_requested = False
        close_browser()

    signal.signal(signal.SIGINT, request_close)
    fltk.Fl.add_idle(close_on_idle)
    try:
        fltk.Fl.run()
    finally:
        fltk.Fl.remove_idle(close_on_idle)
        signal.signal(signal.SIGINT, previous_sigint_handler)


@dataclass(slots=True)
class CommandResult:
    label: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    output: str
    show_transcript: bool = True
    refresh_runs: bool = True
    on_completed: Callable[[CommandResult], None] | None = None


@dataclass(slots=True)
class ViewerRenderResult:
    request_id: int
    artifact_name: str
    html: str
    status_text: str


class ArtifactBrowserWindow:
    def __init__(
        self,
        *,
        data_dir: Path,
        initial_run_id: str | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.initial_run_id = initial_run_id
        self.ui_state_path = DEFAULT_UI_STATE_PATH
        self.appearance_mode = normalize_appearance_mode(
            load_ui_state(self.ui_state_path).get("appearance_mode")
        )
        self.theme: UiTheme = resolve_ui_theme(self.appearance_mode)
        apply_fltk_theme_defaults(fltk, self.theme)
        self.repo_root = Path(__file__).resolve().parents[3]
        self.cli_executable = self._resolve_cli_executable()
        self.command_results: Queue[CommandResult] = Queue()
        self.viewer_render_results: Queue[ViewerRenderResult] = Queue()
        self.run_list_header_boxes: list[object] = []
        self.run_list_layout_signature: tuple[int, tuple[str, ...]] | None = None
        self.artifact_cache: dict[
            str, tuple[list[ArtifactRecord], list[ArtifactSectionRecord]]
        ] = {}
        self.pending_viewer_request_id = 0
        self.viewer_render_future: Future[ViewerRenderResult] | None = None
        self.viewer_render_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="xs2n-ui-preview",
        )
        self.preferences_window = RunPreferencesWindow(
            appearance_mode=self.appearance_mode,
            theme=self.theme,
            on_appearance_mode_changed=self._on_appearance_mode_changed,
            on_run_list_preferences_changed=self._on_run_list_preferences_changed,
        )
        self.auth_window = AuthWindow(
            on_action_requested=self._on_auth_action_requested
        )
        self.auth_snapshot: AuthDoctorResult | None = None
        self.run_list_column_keys = (
            self.preferences_window.current_run_list_column_keys()
        )
        self.focus_mode_enabled = False
        self.standard_pane_widths = (LEFT_PANE_WIDTH, MIDDLE_PANE_WIDTH)
        self.running_label: str | None = None
        self.running_thread: threading.Thread | None = None
        self.selected_run_id: str | None = initial_run_id
        self.selected_artifact_name: str | None = None
        self.pending_viewer_artifact_name: str | None = None
        self.rendered_viewer_artifact_name: str | None = None
        self.runs: list[RunRecord] = []
        self.artifacts: list[ArtifactRecord] = []
        self.sections: list[ArtifactSectionRecord] = []

        self.window = fltk.Fl_Double_Window(
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
            APP_NAME,
        )
        self._build_window()
        self._apply_theme_to_widgets()
        self.preferences_window.apply_theme(self.theme)
        self.auth_window.apply_theme(self.theme)
        self.refresh_runs()
        fltk.Fl.add_idle(self._drain_idle_work)

    def show(self) -> None:
        prepare_macos_app_menu()
        self.window.show()
        apply_macos_app_menu(APP_NAME)

    def _current_theme(self) -> UiTheme:
        return getattr(self, "theme", CLASSIC_LIGHT_THEME)

    def _build_window(self) -> None:
        self._configure_tooltips(self._current_theme())
        tile_y = MENU_HEIGHT + COMMAND_HEIGHT
        tile_height = WINDOW_HEIGHT - tile_y - STATUS_HEIGHT
        right_pane_x = LEFT_PANE_WIDTH + MIDDLE_PANE_WIDTH
        right_pane_width = WINDOW_WIDTH - right_pane_x

        self.window.begin()
        self._style_widget(self.window, label_size=14)

        self.menu_bar = fltk.Fl_Menu_Bar(0, 0, WINDOW_WIDTH, MENU_HEIGHT)
        self._style_widget(
            self.menu_bar,
            label_size=MENU_LABEL_SIZE,
            text_size=MENU_TEXT_SIZE,
        )
        self.menu_bar.add("&File/&Refresh", 0, self._on_refresh_clicked, None)
        self.menu_bar.add("&File/&Preferences", 0, self._on_preferences_clicked, None)
        self.menu_bar.add("&File/&Authentication", 0, self._on_auth_clicked, None)
        self.menu_bar.add(
            RUN_MENU_LAUNCH_LABELS[0],
            0,
            self._on_refresh_following_clicked,
            None,
        )
        self.menu_bar.add(
            RUN_MENU_LAUNCH_LABELS[1],
            0,
            self._on_run_latest_clicked,
            None,
        )
        self.menu_bar.add("&File/&Quit", 0, self._on_quit_clicked, None)

        button_y = MENU_HEIGHT + (COMMAND_HEIGHT - COMMAND_BUTTON_HEIGHT) // 2
        primary_run_button_x = (
            COMMAND_STRIP_PADDING + COMMAND_BUTTON_WIDTH + COMMAND_BUTTON_GAP
        )
        focus_button_x = WINDOW_WIDTH - COMMAND_STRIP_PADDING - COMMAND_BUTTON_WIDTH

        self.command_strip = fltk.Fl_Box(
            0,
            MENU_HEIGHT,
            WINDOW_WIDTH,
            COMMAND_HEIGHT,
        )
        self.command_strip.box(fltk.FL_FLAT_BOX)
        self.command_strip.color(COMMAND_STRIP_COLOR)

        self.refresh_button = fltk.Fl_Button(
            COMMAND_STRIP_PADDING,
            button_y,
            COMMAND_BUTTON_WIDTH,
            COMMAND_BUTTON_HEIGHT,
            "@refresh",
        )
        self._style_command_button(
            self.refresh_button,
            tooltip="Refresh the run list from disk.",
        )
        self.refresh_button.callback(self._on_refresh_clicked, None)

        self.run_latest_button = fltk.Fl_Button(
            primary_run_button_x,
            button_y,
            COMMAND_BUTTON_WIDTH,
            COMMAND_BUTTON_HEIGHT,
            PRIMARY_RUN_BUTTON_SYMBOL,
        )
        self._style_command_button(
            self.run_latest_button,
            tooltip=PRIMARY_RUN_BUTTON_TOOLTIP,
        )
        self.run_latest_button.shortcut(fltk.FL_Enter)
        self.run_latest_button.callback(self._on_run_latest_clicked, None)

        self.focus_mode_button = fltk.Fl_Toggle_Button(
            focus_button_x,
            button_y,
            COMMAND_BUTTON_WIDTH,
            COMMAND_BUTTON_HEIGHT,
            FOCUS_BUTTON_SYMBOL,
        )
        self._style_command_button(
            self.focus_mode_button,
            tooltip="Toggle focus mode and show only the viewer pane.",
        )
        self.focus_mode_button.callback(self._on_focus_mode_toggled, None)

        self.tile = fltk.Fl_Tile(0, tile_y, WINDOW_WIDTH, tile_height)
        self.tile.begin()

        self.run_list_group = fltk.Fl_Group(
            0,
            tile_y,
            LEFT_PANE_WIDTH,
            tile_height,
        )
        self.run_list_group.begin()

        self.run_list_header_background = fltk.Fl_Box(
            0,
            tile_y,
            LEFT_PANE_WIDTH,
            RUN_LIST_HEADER_HEIGHT,
            "",
        )
        self.run_list_header_background.box(fltk.FL_THIN_UP_BOX)
        self.run_list_header_background.color(RUN_LIST_HEADER_COLOR)

        for _column in RUN_LIST_COLUMNS:
            header_box = fltk.Fl_Box(
                0,
                tile_y,
                0,
                RUN_LIST_HEADER_HEIGHT,
                "",
            )
            header_box.box(fltk.FL_THIN_UP_BOX)
            header_box.color(RUN_LIST_HEADER_CELL_COLOR)
            header_box.align(
                fltk.FL_ALIGN_LEFT | fltk.FL_ALIGN_INSIDE | fltk.FL_ALIGN_CLIP
            )
            self._style_widget(header_box, label_size=12, bold=True)
            self.run_list_header_boxes.append(header_box)

        self.runs_browser = RunListBrowser(
            0,
            tile_y + RUN_LIST_HEADER_HEIGHT,
            LEFT_PANE_WIDTH,
            tile_height - RUN_LIST_HEADER_HEIGHT,
            on_delete_requested=self._on_delete_selected_runs_requested,
        )
        self._style_runs_browser(self.runs_browser)
        self.runs_browser.callback(self._on_run_selected, None)
        self.run_list_group.end()
        self.run_list_group.resizable(self.runs_browser)

        middle_pane_x = LEFT_PANE_WIDTH
        middle_pane_y = tile_y
        middle_pane_width = MIDDLE_PANE_WIDTH
        middle_pane_height = tile_height
        raw_files_y = (
            middle_pane_y
            + NAVIGATION_HEADER_HEIGHT
            + SECTIONS_BROWSER_HEIGHT
            + NAVIGATION_PANE_GAP
            + NAVIGATION_HEADER_HEIGHT
        )
        raw_files_height = middle_pane_height - (
            NAVIGATION_HEADER_HEIGHT
            + SECTIONS_BROWSER_HEIGHT
            + NAVIGATION_PANE_GAP
            + NAVIGATION_HEADER_HEIGHT
        )

        self.navigation_group = fltk.Fl_Group(
            middle_pane_x,
            middle_pane_y,
            middle_pane_width,
            middle_pane_height,
        )
        self.navigation_group.begin()

        self.sections_header = self._create_panel_header(
            middle_pane_x,
            middle_pane_y,
            middle_pane_width,
            NAVIGATION_HEADER_HEIGHT,
            "Sections",
        )
        self.sections_browser = fltk.Fl_Hold_Browser(
            middle_pane_x,
            middle_pane_y + NAVIGATION_HEADER_HEIGHT,
            middle_pane_width,
            SECTIONS_BROWSER_HEIGHT,
        )
        self._style_browser(self.sections_browser, text_size=13)
        self.sections_browser.tooltip(
            "Curated shortcuts for the most important artifacts in the selected run."
        )
        self.sections_browser.callback(self._on_section_selected, None)

        self.raw_files_header = self._create_panel_header(
            middle_pane_x,
            middle_pane_y + NAVIGATION_HEADER_HEIGHT + SECTIONS_BROWSER_HEIGHT + NAVIGATION_PANE_GAP,
            middle_pane_width,
            NAVIGATION_HEADER_HEIGHT,
            "Raw Files",
        )
        self.raw_files_browser = fltk.Fl_Hold_Browser(
            middle_pane_x,
            raw_files_y,
            middle_pane_width,
            raw_files_height,
        )
        self._style_browser(self.raw_files_browser)
        self.raw_files_browser.tooltip(
            "Every visible file and directory in the selected run folder."
        )
        self.raw_files_browser.callback(self._on_raw_file_selected, None)

        self.navigation_group.end()
        self.navigation_group.resizable(self.raw_files_browser)

        self.viewer = fltk.Fl_Help_View(
            right_pane_x,
            tile_y,
            right_pane_width,
            tile_height,
            "Viewer",
        )
        self.viewer.box(fltk.FL_BORDER_BOX)
        self._style_widget(self.viewer, label_size=13, text_size=14)
        self._configure_viewer_links()

        self.tile.end()

        self.status_output = fltk.Fl_Output(
            0,
            WINDOW_HEIGHT - STATUS_HEIGHT,
            WINDOW_WIDTH,
            STATUS_HEIGHT,
        )
        self.status_output.box(fltk.FL_FLAT_BOX)
        self._style_widget(self.status_output, text_size=12)
        self.status_output.value(
            f"Ready. Browsing run artifacts under {self.data_dir}."
        )

        self.window.end()
        self.window.resizable(self.tile)
        self.window.callback(self._on_quit_clicked, None)
        self._sync_focus_mode_button()

    def refresh_runs(self) -> None:
        self.runs = scan_runs(self.data_dir)
        self.artifact_cache = {}
        self._refresh_run_list_rows()
        self._sync_run_list_layout(force=True)

        if not self.runs:
            self.selected_run_id = None
            self.selected_artifact_name = None
            self._clear_artifact_viewer_state()
            self.artifacts = []
            self.sections = []
            self._set_run_browser_selection(
                selected_indexes=[],
                active_index=None,
            )
            self.sections_browser.clear()
            self.raw_files_browser.clear()
            self._set_viewer_html(
                render_plain_text_html(
                    title="No Runs Discovered Yet",
                    body=(
                        "This browser scans every data/report_runs* directory "
                        "and reads whatever artifacts already exist on disk.\n\n"
                        "Run `xs2n report latest` to create a fresh run folder."
                    ),
                    metadata={"data_dir": str(self.data_dir)},
                    theme=self._current_theme(),
                )
            )
            self.status_output.value(
                f"No run folders found in {self.data_dir}."
            )
            return

        selected_index = self._resolve_selected_run_index()
        self._set_run_browser_selection(
            selected_indexes=[selected_index],
            active_index=selected_index,
        )
        self._apply_selected_run(selected_index)

    def _refresh_run_list_rows(self) -> None:
        self.runs_browser.clear()
        for run in self.runs:
            self.runs_browser.add(
                format_run_list_row(
                    run,
                    column_keys=self.run_list_column_keys,
                )
            )

    def _on_run_list_preferences_changed(
        self,
        column_keys: tuple[str, ...],
    ) -> None:
        self.run_list_column_keys = column_keys
        self._refresh_run_list_rows()
        if self.runs:
            selected_index = self._resolve_selected_run_index()
            self._set_run_browser_selection(
                selected_indexes=[selected_index],
                active_index=selected_index,
            )
        else:
            self._set_run_browser_selection(
                selected_indexes=[],
                active_index=None,
            )
        self._sync_run_list_layout(force=True)
        self.status_output.value("Run list columns updated.")

    def _on_appearance_mode_changed(self, mode: str) -> None:
        normalized_mode = normalize_appearance_mode(mode)
        if normalized_mode == getattr(self, "appearance_mode", "system"):
            return

        self.appearance_mode = normalized_mode
        save_ui_state(
            {"appearance_mode": self.appearance_mode},
            getattr(self, "ui_state_path", None),
        )
        self.theme = resolve_ui_theme(self.appearance_mode)
        apply_fltk_theme_defaults(fltk, self.theme)
        self._apply_theme_to_widgets()
        self.preferences_window.apply_theme(self.theme)
        auth_window = getattr(self, "auth_window", None)
        if auth_window is not None:
            auth_window.apply_theme(self.theme)
        self.refresh_runs()

    def _sync_run_list_layout(self, *, force: bool = False) -> None:
        layout_signature = (self.runs_browser.w(), self.run_list_column_keys)
        if not force and layout_signature == self.run_list_layout_signature:
            return

        visible_columns = visible_run_list_columns(self.run_list_column_keys)
        column_widths = compute_run_list_widths(
            self.runs_browser.w(),
            column_keys=self.run_list_column_keys,
        )

        self.runs_browser.column_char("\t")
        self.runs_browser.column_widths((*column_widths, 0))
        self.runs_browser.tooltip(
            "Columns: " + ", ".join(column.label for column in visible_columns) + "."
        )
        self._layout_run_list_headers(
            visible_columns=visible_columns,
            column_widths=column_widths,
        )
        self.run_list_layout_signature = layout_signature
        self.runs_browser.redraw()

    def _layout_run_list_headers(
        self,
        *,
        visible_columns,
        column_widths: tuple[int, ...],
    ) -> None:  # noqa: ANN001
        current_x = self.run_list_header_background.x()
        header_y = self.run_list_header_background.y()
        header_height = self.run_list_header_background.h()

        for index, header_box in enumerate(self.run_list_header_boxes):
            if index >= len(visible_columns):
                header_box.hide()
                continue

            column = visible_columns[index]
            width = column_widths[index]
            header_box.label(f" {column.label}")
            header_box.tooltip(column.tooltip)
            header_box.resize(current_x, header_y, width, header_height)
            header_box.show()
            current_x += width

        self.run_list_header_background.redraw()

    def _on_focus_mode_toggled(self, widget=None, data=None) -> None:  # noqa: ANN001
        enabled = bool(widget.value()) if widget is not None else False
        self._set_focus_mode(enabled=enabled)

    def _set_focus_mode(self, *, enabled: bool) -> None:
        if enabled == self.focus_mode_enabled:
            self._sync_focus_mode_button()
            return

        if enabled:
            self.standard_pane_widths = (
                self.run_list_group.w(),
                self.navigation_group.w(),
            )
            self.run_list_group.hide()
            self.navigation_group.hide()
            self.viewer.resize(
                self.tile.x(),
                self.tile.y(),
                self.tile.w(),
                self.tile.h(),
            )
            self.focus_mode_enabled = True
            self.tile.init_sizes()
            self.tile.redraw()
            self.status_output.value(
                "Focus mode enabled. Showing the viewer only."
            )
            self._sync_focus_mode_button()
            return

        self.focus_mode_enabled = False
        self._layout_standard_panes(
            left_pane_width=self.standard_pane_widths[0],
            middle_pane_width=self.standard_pane_widths[1],
        )
        self.run_list_group.show()
        self.navigation_group.show()
        self._sync_run_list_layout(force=True)
        self.tile.init_sizes()
        self.tile.redraw()
        self.status_output.value(
            "Focus mode disabled. Restored all three panes."
        )
        self._sync_focus_mode_button()

    def _layout_standard_panes(
        self,
        *,
        left_pane_width: int,
        middle_pane_width: int,
    ) -> None:
        tile_x = self.tile.x()
        tile_y = self.tile.y()
        tile_width = self.tile.w()
        tile_height = self.tile.h()
        left_width, middle_width = self._resolve_standard_pane_widths(
            tile_width=tile_width,
            left_pane_width=left_pane_width,
            middle_pane_width=middle_pane_width,
        )
        right_pane_x = tile_x + left_width + middle_width
        right_pane_width = max(1, tile_width - left_width - middle_width)

        self.run_list_group.resize(
            tile_x,
            tile_y,
            left_width,
            tile_height,
        )
        self.run_list_header_background.resize(
            tile_x,
            tile_y,
            left_width,
            RUN_LIST_HEADER_HEIGHT,
        )
        self.runs_browser.resize(
            tile_x,
            tile_y + RUN_LIST_HEADER_HEIGHT,
            left_width,
            tile_height - RUN_LIST_HEADER_HEIGHT,
        )

        middle_pane_x = tile_x + left_width
        raw_files_header_y = (
            tile_y
            + NAVIGATION_HEADER_HEIGHT
            + SECTIONS_BROWSER_HEIGHT
            + NAVIGATION_PANE_GAP
        )
        raw_files_y = raw_files_header_y + NAVIGATION_HEADER_HEIGHT
        raw_files_height = max(
            1,
            tile_height
            - (
                NAVIGATION_HEADER_HEIGHT
                + SECTIONS_BROWSER_HEIGHT
                + NAVIGATION_PANE_GAP
                + NAVIGATION_HEADER_HEIGHT
            ),
        )

        self.navigation_group.resize(
            middle_pane_x,
            tile_y,
            middle_width,
            tile_height,
        )
        self.sections_header.resize(
            middle_pane_x,
            tile_y,
            middle_width,
            NAVIGATION_HEADER_HEIGHT,
        )
        self.sections_browser.resize(
            middle_pane_x,
            tile_y + NAVIGATION_HEADER_HEIGHT,
            middle_width,
            SECTIONS_BROWSER_HEIGHT,
        )
        self.raw_files_header.resize(
            middle_pane_x,
            raw_files_header_y,
            middle_width,
            NAVIGATION_HEADER_HEIGHT,
        )
        self.raw_files_browser.resize(
            middle_pane_x,
            raw_files_y,
            middle_width,
            raw_files_height,
        )

        self.viewer.resize(
            right_pane_x,
            tile_y,
            right_pane_width,
            tile_height,
        )

    @staticmethod
    def _resolve_standard_pane_widths(
        *,
        tile_width: int,
        left_pane_width: int,
        middle_pane_width: int,
    ) -> tuple[int, int]:
        left_width = max(1, left_pane_width)
        middle_width = max(1, middle_pane_width)
        viewer_min_width = min(
            VIEWER_MIN_WIDTH,
            max(1, tile_width - 2),
        )
        max_navigation_width = max(2, tile_width - viewer_min_width)

        if left_width + middle_width <= max_navigation_width:
            return left_width, middle_width

        total_requested_width = max(1, left_width + middle_width)
        scaled_left_width = max(
            1,
            int((left_width * max_navigation_width) / total_requested_width),
        )
        scaled_middle_width = max(1, max_navigation_width - scaled_left_width)

        if scaled_left_width + scaled_middle_width > max_navigation_width:
            scaled_middle_width = max(1, max_navigation_width - scaled_left_width)

        return scaled_left_width, scaled_middle_width

    def _sync_focus_mode_button(self) -> None:
        self.focus_mode_button.value(int(self.focus_mode_enabled))
        if self.focus_mode_enabled:
            self.focus_mode_button.tooltip(
                "Focus mode is on. Click to restore the run and navigation panes."
            )
        else:
            self.focus_mode_button.tooltip(
                "Focus mode is off. Click to show only the viewer pane."
            )
        self.focus_mode_button.redraw()

    def _resolve_selected_run_index(self) -> int:
        if self.selected_run_id is not None:
            for index, run in enumerate(self.runs):
                if run.run_id == self.selected_run_id:
                    return index
        return 0

    def _selected_run_indexes(self) -> list[int]:
        return selected_run_indexes(self.runs_browser, row_count=len(self.runs))

    def _set_run_browser_selection(
        self,
        *,
        selected_indexes: list[int],
        active_index: int | None,
    ) -> None:
        if hasattr(self.runs_browser, "set_selection"):
            self.runs_browser.set_selection(
                selected_indexes=selected_indexes,
                active_index=active_index,
            )
            return

        if active_index is None:
            self.runs_browser.value(0)
            return
        self.runs_browser.value(active_index + 1)

    def _apply_selected_run(self, index: int) -> None:
        run = self.runs[index]
        self.selected_run_id = run.run_id

        cache_key = str(run.run_dir)
        cached_artifacts = self.artifact_cache.get(cache_key)
        if cached_artifacts is None:
            artifacts = list_run_artifacts(run)
            cached_artifacts = (
                artifacts,
                list_artifact_sections(artifacts),
            )
            self.artifact_cache[cache_key] = cached_artifacts
        self.artifacts, self.sections = cached_artifacts
        self.sections_browser.clear()
        for section in self.sections:
            self.sections_browser.add(section.browser_label)

        self.raw_files_browser.clear()
        for artifact in self.artifacts:
            self.raw_files_browser.add(artifact.name)

        if not self.artifacts:
            self.selected_artifact_name = None
            self._clear_artifact_viewer_state()
            self.sections_browser.value(0)
            self.raw_files_browser.value(0)
            self._set_viewer_html(
                render_plain_text_html(
                    title=f"{run.run_id} Has No Visible Artifacts Yet",
                    body="This run folder exists, but no inspectable artifacts were found.",
                    metadata={"run_id": run.run_id},
                    theme=self._current_theme(),
                )
            )
            return

        preferred_artifact_name = self._resolve_selected_artifact_name()
        if preferred_artifact_name is None:
            return
        self._apply_selected_artifact_name(preferred_artifact_name)

    def _resolve_selected_artifact_name(self) -> str | None:
        if self.selected_artifact_name is not None:
            artifact = self._find_artifact(self.selected_artifact_name)
            if artifact is not None:
                return artifact.name
        if self._find_artifact("digest.html") is not None:
            return "digest.html"
        if self._find_artifact("digest.md") is not None:
            return "digest.md"
        if not self.artifacts:
            return None
        return self.artifacts[0].name

    def _find_artifact(self, artifact_name: str) -> ArtifactRecord | None:
        for artifact in self.artifacts:
            if artifact.name == artifact_name:
                return artifact
        return None

    def _artifact_index_for_name(self, artifact_name: str) -> int | None:
        for index, artifact in enumerate(self.artifacts):
            if artifact.name == artifact_name:
                return index
        return None

    def _section_index_for_artifact_name(self, artifact_name: str) -> int | None:
        for index, section in enumerate(self.sections):
            if section.artifact_name == artifact_name:
                return index
        return None

    def _sync_navigation_selection(self, artifact_name: str) -> None:
        section_index = self._section_index_for_artifact_name(artifact_name)
        self.sections_browser.value(0 if section_index is None else section_index + 1)

        raw_file_index = self._artifact_index_for_name(artifact_name)
        self.raw_files_browser.value(
            0 if raw_file_index is None else raw_file_index + 1
        )

    def _apply_selected_artifact_name(self, artifact_name: str) -> None:
        artifact = self._find_artifact(artifact_name)
        if artifact is None:
            return
        self.selected_artifact_name = artifact.name
        self._sync_navigation_selection(artifact.name)
        self.pending_viewer_artifact_name = artifact.name
        self.rendered_viewer_artifact_name = None
        try:
            loading_html = render_loading_artifact_html(
                artifact,
                theme=self._current_theme(),
            )
        except TypeError:
            loading_html = render_loading_artifact_html(artifact)
        self._set_viewer_html(loading_html)
        self.status_output.value(f"Loading {artifact.name}...")
        self._schedule_artifact_preview_render(artifact)

    def _clear_artifact_viewer_state(self) -> None:
        self.pending_viewer_request_id = getattr(
            self,
            "pending_viewer_request_id",
            0,
        ) + 1
        self.pending_viewer_artifact_name = None
        self.rendered_viewer_artifact_name = None
        future = getattr(self, "viewer_render_future", None)
        if future is not None and not future.done():
            future.cancel()

    def _drain_pending_viewer_render(self) -> None:
        latest_result: ViewerRenderResult | None = None
        while True:
            try:
                result = self.viewer_render_results.get_nowait()
            except Empty:
                break

            if result.request_id != self.pending_viewer_request_id:
                continue
            if self.selected_artifact_name != result.artifact_name:
                continue
            latest_result = result

        if latest_result is None:
            return

        self.pending_viewer_artifact_name = None
        self._set_viewer_html(latest_result.html)
        self.rendered_viewer_artifact_name = latest_result.artifact_name
        if self.selected_artifact_name == latest_result.artifact_name:
            self.status_output.value(latest_result.status_text)

    def _schedule_artifact_preview_render(self, artifact: ArtifactRecord) -> None:
        self.pending_viewer_request_id += 1
        request_id = self.pending_viewer_request_id
        future = self.viewer_render_future
        if future is not None and not future.done():
            future.cancel()
        self.viewer_render_future = self.viewer_render_executor.submit(
            self._build_viewer_render_result,
            request_id=request_id,
            artifact=artifact,
            theme=self._current_theme(),
        )
        self.viewer_render_future.request_id = request_id  # type: ignore[attr-defined]
        self.viewer_render_future.artifact_name = artifact.name  # type: ignore[attr-defined]
        self.viewer_render_future.add_done_callback(
            self._on_viewer_render_future_done
        )

    @staticmethod
    def _build_viewer_render_result(
        *,
        request_id: int,
        artifact: ArtifactRecord,
        theme: UiTheme,
    ) -> ViewerRenderResult:
        try:
            html = render_artifact_html(artifact, theme=theme)
            status_text = f"Viewing {artifact.name}."
        except Exception as error:
            html = render_plain_text_html(
                title=f"Failed to render {artifact.name}",
                body=f"{error.__class__.__name__}: {error}\n",
                metadata={"path": str(artifact.path)},
                theme=theme,
            )
            status_text = f"Failed to render {artifact.name}."
        return ViewerRenderResult(
            request_id=request_id,
            artifact_name=artifact.name,
            html=html,
            status_text=status_text,
        )

    def _on_viewer_render_future_done(self, future: Future[ViewerRenderResult]) -> None:
        if future.cancelled():
            return
        try:
            result = future.result()
        except Exception as error:
            request_id = getattr(
                future,
                "request_id",
                self.pending_viewer_request_id,
            )
            artifact_name = getattr(
                future,
                "artifact_name",
                self.selected_artifact_name or "unknown",
            )
            result = ViewerRenderResult(
                request_id=request_id,
                artifact_name=artifact_name,
                html=render_plain_text_html(
                    title=f"Failed to render {artifact_name}",
                    body=f"{error.__class__.__name__}: {error}\n",
                    theme=self._current_theme(),
                ),
                status_text=f"Failed to render {artifact_name}.",
            )
        self.viewer_render_results.put(result)
        try:
            fltk.Fl.awake()
        except Exception:
            return

    def _start_command(
        self,
        *,
        label: str,
        args: list[str],
        show_transcript: bool = True,
        refresh_runs: bool = True,
        on_completed: Callable[[CommandResult], None] | None = None,
        starting_status: str | None = None,
    ) -> None:
        if self.running_thread is not None and self.running_thread.is_alive():
            fltk.fl_alert(
                f"`{self.running_label}` is still running. Wait for it to finish first."
            )
            return

        command = [self.cli_executable, *args]
        self.running_label = label
        self._clear_artifact_viewer_state()
        if starting_status is not None:
            self.status_output.value(starting_status)
        elif show_transcript:
            self.status_output.value(f"Running {label}...")

        if show_transcript:
            self._set_viewer_html(
                render_plain_text_html(
                    title=f"Running {label}",
                    body=f"$ {' '.join(command)}\n\nStarting background command...\n",
                    metadata={"cwd": str(self.repo_root)},
                    theme=self._current_theme(),
                )
            )

        def worker() -> None:
            completed = subprocess.run(
                command,
                cwd=self.repo_root,
                text=True,
                capture_output=True,
                check=False,
            )
            transcript_parts = [f"$ {' '.join(command)}", ""]
            if completed.stdout:
                transcript_parts.extend(["stdout:", completed.stdout.rstrip(), ""])
            if completed.stderr:
                transcript_parts.extend(["stderr:", completed.stderr.rstrip(), ""])
            transcript_parts.append(f"exit_code: {completed.returncode}")
            self.command_results.put(
                CommandResult(
                    label=label,
                    command=command,
                    returncode=completed.returncode,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                    output="\n".join(transcript_parts).rstrip() + "\n",
                    show_transcript=show_transcript,
                    refresh_runs=refresh_runs,
                    on_completed=on_completed,
                )
            )

        self.running_thread = threading.Thread(target=worker, daemon=True)
        self.running_thread.start()

    def _start_run_command(self, command: RunCommand) -> None:
        self._start_command(label=command.label, args=command.args)

    def _drain_idle_work(self, _data=None) -> None:  # noqa: ANN001
        while True:
            try:
                result = self.command_results.get_nowait()
            except Empty:
                break

            self.running_label = None
            self.running_thread = None

            if result.show_transcript:
                self._clear_artifact_viewer_state()
                self._set_viewer_html(
                    render_plain_text_html(
                        title=result.label,
                        body=result.output,
                        metadata={"exit_code": str(result.returncode)},
                        theme=self._current_theme(),
                    )
                )

            if result.show_transcript:
                if result.returncode == 0:
                    self.status_output.value(f"{result.label} finished successfully.")
                else:
                    self.status_output.value(
                        f"{result.label} failed with exit code {result.returncode}."
                    )

            if result.on_completed is not None:
                result.on_completed(result)

            if result.refresh_runs:
                self.refresh_runs()

        self._drain_pending_viewer_render()
        self._sync_run_list_layout()

    def _on_refresh_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        self.refresh_runs()
        self.status_output.value("Run list refreshed.")

    def _on_preferences_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        self.preferences_window.show()

    def _on_auth_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        self._refresh_auth_state(
            show_window=True,
            starting_status="Refreshing authentication status...",
        )

    def _current_cookies_file(self) -> Path:
        return self.preferences_window.applied_latest_arguments.cookies_file

    @staticmethod
    def _build_auth_error_snapshot(detail: str) -> AuthDoctorResult:
        return AuthDoctorResult(
            codex=ProviderStatus(
                status="error",
                summary="Authentication status check failed.",
                detail=detail,
            ),
            x=ProviderStatus(
                status="error",
                summary="Authentication status check failed.",
                detail=detail,
            ),
            run_readiness=RunReadiness(
                digest_ready=False,
                latest_ready=False,
            ),
        )

    def _update_auth_snapshot(self, snapshot: AuthDoctorResult) -> None:
        self.auth_snapshot = snapshot
        self.auth_window.update_snapshot(
            snapshot=snapshot,
            cookies_file=self._current_cookies_file(),
        )

    def _refresh_auth_state(
        self,
        *,
        pending_command: RunCommand | None = None,
        show_window: bool = False,
        starting_status: str | None = None,
    ) -> None:
        if show_window:
            self.auth_window.show()

        if self._has_running_command():
            return

        command = build_auth_doctor_command(self._current_cookies_file())
        self._start_command(
            label=command.label,
            args=command.args,
            show_transcript=False,
            refresh_runs=False,
            starting_status=starting_status,
            on_completed=lambda result, pending_command=pending_command: self._handle_auth_doctor_command_result(
                result=result,
                pending_command=pending_command,
            ),
        )

    def _handle_auth_doctor_command_result(
        self,
        *,
        result: CommandResult,
        pending_command: RunCommand | None = None,
    ) -> None:
        if result.returncode != 0:
            snapshot = self._build_auth_error_snapshot(
                result.stderr.strip() or result.stdout.strip() or result.output.strip()
            )
            self._update_auth_snapshot(snapshot)
            self.status_output.value("Authentication status refresh failed.")
            if pending_command is not None:
                self.auth_window.show()
            return

        try:
            snapshot = AuthDoctorResult.model_validate_json(result.stdout)
        except Exception:
            snapshot = self._build_auth_error_snapshot(
                "Could not parse `xs2n auth doctor --json` output."
            )
            self._update_auth_snapshot(snapshot)
            self.status_output.value("Authentication status refresh failed.")
            if pending_command is not None:
                self.auth_window.show()
            return

        self._update_auth_snapshot(snapshot)
        if pending_command is None:
            self.status_output.value("Authentication status refreshed.")
            return

        self._handle_run_auth_doctor_result(
            snapshot=snapshot,
            command=pending_command,
        )

    def _handle_run_auth_doctor_result(
        self,
        *,
        snapshot: AuthDoctorResult,
        command: RunCommand,
    ) -> None:
        self._update_auth_snapshot(snapshot)

        if command.label == "report latest":
            if snapshot.run_readiness.latest_ready:
                self._start_run_command(command)
                return
            self.auth_window.show()
            self.status_output.value(
                "Cannot start report latest until Codex and X / Twitter are ready."
            )
            return

        if command.label == "report issues":
            if snapshot.run_readiness.digest_ready:
                self._start_run_command(command)
                return
            self.auth_window.show()
            self.status_output.value(
                "Cannot start report issues until Codex is ready."
            )
            return

        self._start_run_command(command)

    def _on_auth_action_requested(self, action: str) -> None:
        if action == "refresh":
            self._refresh_auth_state(
                show_window=True,
                starting_status="Refreshing authentication status...",
            )
            return

        cookies_file = self._current_cookies_file()
        if action == "codex_login":
            command = build_codex_login_command()
        elif action == "codex_logout":
            command = build_codex_logout_command()
        elif action == "x_login":
            command = build_x_login_command(cookies_file)
        elif action == "x_reset":
            command = build_x_reset_command(cookies_file)
        else:
            return

        self.auth_window.show()
        self._start_command(
            label=command.label,
            args=command.args,
            refresh_runs=False,
            on_completed=lambda result: self._refresh_auth_state(
                show_window=True,
                starting_status="Refreshing authentication status...",
            ),
        )

    def _on_run_digest_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        try:
            command = self.preferences_window.current_digest_command()
        except ValueError as error:
            self.preferences_window.show_digest_tab()
            fltk.fl_alert(str(error))
            return
        self._refresh_auth_state(
            pending_command=command,
            starting_status="Checking authentication before report issues...",
        )

    def _on_refresh_following_clicked(
        self,
        widget=None,
        data=None,
    ) -> None:  # noqa: ANN001
        command = self.preferences_window.current_following_refresh_command()
        self._start_run_command(command)

    def _on_run_latest_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        try:
            command = self.preferences_window.current_latest_command()
        except ValueError as error:
            self.preferences_window.show_latest_tab()
            fltk.fl_alert(str(error))
            return
        self._refresh_auth_state(
            pending_command=command,
            starting_status="Checking authentication before report latest...",
        )

    def _has_running_command(self) -> bool:
        return (
            getattr(self, "running_thread", None) is not None
            and self.running_thread.is_alive()
        )

    def _confirm_close_browser(self) -> bool:
        if not self._has_running_command():
            return True

        running_label = self.running_label or "background command"
        choice = fltk.fl_choice(
            (
                f"`{running_label}` is still running.\n"
                "Quit the UI anyway? The run may be interrupted."
            ),
            "Stay Open",
            "Quit",
            None,
        )
        return choice == 1

    def _on_delete_selected_runs_requested(self) -> None:
        if self._has_running_command():
            running_label = self.running_label or "background command"
            fltk.fl_alert(
                f"`{running_label}` is still running. Wait for it to finish first."
            )
            return

        selected_indexes = self._selected_run_indexes()
        if not selected_indexes:
            fltk.fl_alert("Select at least one run to delete.")
            return

        selected_runs = [self.runs[index] for index in selected_indexes]
        choice = fltk.fl_choice(
            delete_selection_message(selected_runs),
            "Cancel",
            "Delete",
            None,
        )
        if choice != 1:
            return

        fallback_run_id = fallback_run_id_after_delete(
            self.runs,
            selected_indexes=selected_indexes,
        )
        try:
            delete_runs(selected_runs)
        except OSError as error:
            fltk.fl_alert(f"Failed to delete selected runs:\n{error}")
            return

        self.selected_run_id = fallback_run_id
        self.selected_artifact_name = None
        self.refresh_runs()
        deleted_count = len(selected_runs)
        noun = "run" if deleted_count == 1 else "runs"
        self.status_output.value(f"Deleted {deleted_count} {noun}.")

    def close_browser(self) -> None:
        if not self._confirm_close_browser():
            return

        executor = getattr(self, "viewer_render_executor", None)
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)
        self.preferences_window.hide()
        auth_window = getattr(self, "auth_window", None)
        if auth_window is not None:
            auth_window.hide()
        self.window.hide()
        fltk.Fl.hide_all_windows()

    def _on_quit_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        self.close_browser()

    def _on_run_selected(self, widget, data=None) -> None:  # noqa: ANN001
        selection = widget.value()
        if selection < 1 or selection > len(self.runs):
            return
        self._apply_selected_run(selection - 1)

    def _on_section_selected(self, widget, data=None) -> None:  # noqa: ANN001
        selection = widget.value()
        if selection < 1 or selection > len(self.sections):
            return
        self._apply_selected_artifact_name(
            self.sections[selection - 1].artifact_name
        )

    def _on_raw_file_selected(self, widget, data=None) -> None:  # noqa: ANN001
        selection = widget.value()
        if selection < 1 or selection > len(self.artifacts):
            return
        self._apply_selected_artifact_name(self.artifacts[selection - 1].name)

    def _resolve_cli_executable(self) -> str:
        argv0 = Path(sys.argv[0])
        if argv0.exists():
            return str(argv0.resolve())
        return "xs2n"

    def _set_viewer_html(self, html: str) -> None:
        self.viewer.value(html)
        self.viewer.topline(0)
        self.viewer.leftline(0)

    def _configure_viewer_links(self) -> None:
        link_method = getattr(self.viewer, "link", None)
        if not callable(link_method):
            return
        self._viewer_link_handler = self._handle_viewer_link
        try:
            link_method(self._viewer_link_handler)
        except Exception:
            return

    def _handle_viewer_link(self, *args) -> str | None:  # noqa: ANN001
        uri = next(
            (arg for arg in reversed(args) if isinstance(arg, str)),
            None,
        )
        if uri is None:
            return None
        thread_id = parse_thread_source_uri(uri)
        if thread_id is not None:
            artifact = self._find_artifact(self.selected_artifact_name or "")
            if artifact is None:
                return None
            html = render_saved_thread_source_html(
                artifact_path=artifact.path,
                thread_id=thread_id,
                theme=self._current_theme(),
            )
            if html is None:
                return None
            issue_thread_title = self._source_snapshot_title(
                artifact=artifact,
                thread_id=thread_id,
            )
            self._set_viewer_html(html)
            self.status_output.value(
                f"Viewing source snapshot for {issue_thread_title}."
            )
            return None

        if uri == INTERNAL_DIGEST_URI:
            artifact = self._find_artifact(self.selected_artifact_name or "")
            if artifact is None:
                return None
            self._set_viewer_html(
                render_artifact_html(artifact, theme=self._current_theme())
            )
            self.status_output.value(f"Viewing {artifact.name}.")
            return None

        if uri.startswith("https://") or uri.startswith("http://"):
            webbrowser.open(uri)
            self.status_output.value("Opened source in your browser.")
            return None

        return uri

    def _source_snapshot_title(self, *, artifact: ArtifactRecord, thread_id: str) -> str:
        preview = load_saved_digest_preview(run_dir=artifact.path.parent)
        if preview is None:
            return thread_id
        _issue, thread = find_saved_issue_thread(preview, thread_id=thread_id)
        if thread is None:
            return thread_id
        return thread.thread_title

    def _apply_theme_to_widgets(self) -> None:
        theme = self._current_theme()
        window_color = to_fltk_color(fltk, theme.window_bg)
        panel_color = to_fltk_color(fltk, theme.panel_bg)
        header_color = to_fltk_color(fltk, theme.header_bg)
        header_cell_color = to_fltk_color(fltk, theme.header_cell_bg)
        panel_bg2_color = to_fltk_color(fltk, theme.panel_bg2)
        text_color = to_fltk_color(fltk, theme.text)
        selection_color = to_fltk_color(fltk, theme.selection_bg)
        viewer_color = to_fltk_color(fltk, theme.viewer_plain_bg)

        if hasattr(self.window, "color"):
            self.window.color(window_color)
        if hasattr(self.menu_bar, "color"):
            self.menu_bar.color(panel_color)
        if hasattr(self.menu_bar, "selection_color"):
            self.menu_bar.selection_color(selection_color)
        if hasattr(self.menu_bar, "labelcolor"):
            self.menu_bar.labelcolor(text_color)
        if hasattr(self.menu_bar, "textcolor"):
            self.menu_bar.textcolor(text_color)

        self.command_strip.color(panel_color)
        for button in (
            self.refresh_button,
            self.run_latest_button,
            self.focus_mode_button,
        ):
            self._apply_theme_to_command_button(button)

        self.run_list_header_background.color(header_color)
        for header_box in self.run_list_header_boxes:
            header_box.color(header_cell_color)
            if hasattr(header_box, "labelcolor"):
                header_box.labelcolor(text_color)

        self._apply_theme_to_browser(self.runs_browser)
        self._apply_theme_to_panel_header(self.sections_header)
        self._apply_theme_to_browser(self.sections_browser)
        self._apply_theme_to_panel_header(self.raw_files_header)
        self._apply_theme_to_browser(self.raw_files_browser)

        if hasattr(self.viewer, "color"):
            self.viewer.color(viewer_color)
        if hasattr(self.viewer, "textcolor"):
            self.viewer.textcolor(text_color)
        if hasattr(self.viewer, "labelcolor"):
            self.viewer.labelcolor(text_color)

        if hasattr(self.status_output, "color"):
            self.status_output.color(panel_color)
        if hasattr(self.status_output, "textcolor"):
            self.status_output.textcolor(text_color)
        if hasattr(self.status_output, "labelcolor"):
            self.status_output.labelcolor(text_color)

        self._configure_tooltips(theme)
        if hasattr(self.runs_browser, "linespacing"):
            self.runs_browser.linespacing(3)
        self.window.redraw()

    def _apply_theme_to_panel_header(self, header) -> None:  # noqa: ANN001
        theme = self._current_theme()
        if hasattr(header, "color"):
            header.color(to_fltk_color(fltk, theme.header_bg))
        if hasattr(header, "labelcolor"):
            header.labelcolor(to_fltk_color(fltk, theme.text))

    def _apply_theme_to_browser(self, browser) -> None:  # noqa: ANN001
        theme = self._current_theme()
        if hasattr(browser, "color"):
            browser.color(to_fltk_color(fltk, theme.panel_bg2))
        if hasattr(browser, "selection_color"):
            browser.selection_color(to_fltk_color(fltk, theme.selection_bg))
        if hasattr(browser, "textcolor"):
            browser.textcolor(to_fltk_color(fltk, theme.text))
        if hasattr(browser, "labelcolor"):
            browser.labelcolor(to_fltk_color(fltk, theme.text))

    def _apply_theme_to_command_button(self, button) -> None:  # noqa: ANN001
        theme = self._current_theme()
        if hasattr(button, "color"):
            button.color(to_fltk_color(fltk, theme.control_bg))
        if hasattr(button, "selection_color"):
            button.selection_color(
                to_fltk_color(fltk, theme.control_pressed_bg)
            )
        if hasattr(button, "labelcolor"):
            button.labelcolor(to_fltk_color(fltk, theme.text))

    def _create_panel_header(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        label: str,
    ):
        header = fltk.Fl_Box(
            x,
            y,
            width,
            height,
            label,
        )
        header.box(fltk.FL_THIN_UP_BOX)
        self._style_widget(header, label_size=12, bold=True)
        return header

    @staticmethod
    def _style_browser(  # noqa: ANN001
        browser,
        *,
        text_size: int = 14,
    ) -> None:
        browser.box(fltk.FL_BORDER_BOX)
        ArtifactBrowserWindow._style_widget(
            browser,
            label_size=13,
            text_size=text_size,
        )

    @staticmethod
    def _style_runs_browser(browser) -> None:  # noqa: ANN001
        ArtifactBrowserWindow._style_browser(browser, text_size=13)
        browser.column_char("\t")
        browser.linespacing(2)

    @staticmethod
    def _configure_tooltips(theme: UiTheme) -> None:
        fltk.Fl_Tooltip.font(fltk.FL_HELVETICA)
        fltk.Fl_Tooltip.size(12)
        fltk.Fl_Tooltip.color(to_fltk_color(fltk, theme.tooltip_bg))
        fltk.Fl_Tooltip.textcolor(to_fltk_color(fltk, theme.tooltip_text))
        fltk.Fl_Tooltip.delay(0.20)
        fltk.Fl_Tooltip.hoverdelay(0.05)

    @staticmethod
    def _style_command_button(
        button,
        *,
        tooltip: str,
        label_size: int = 16,
    ) -> None:  # noqa: ANN001
        button.box(fltk.FL_THIN_UP_BOX)
        button.down_box(fltk.FL_THIN_DOWN_BOX)
        button.color(COMMAND_BUTTON_COLOR)
        button.selection_color(COMMAND_BUTTON_PRESSED_COLOR)
        button.labelfont(fltk.FL_HELVETICA)
        button.labelsize(label_size)
        button.labelcolor(COMMAND_TEXT_COLOR)
        button.tooltip(tooltip)
        button.clear_visible_focus()

    @staticmethod
    def _style_widget(  # noqa: ANN001
        widget,
        *,
        label_size: int | None = None,
        text_size: int | None = None,
        bold: bool = False,
    ) -> None:
        font = fltk.FL_HELVETICA_BOLD if bold else fltk.FL_HELVETICA
        if hasattr(widget, "labelfont"):
            widget.labelfont(font)
        if label_size is not None and hasattr(widget, "labelsize"):
            widget.labelsize(label_size)
        if text_size is not None and hasattr(widget, "textfont"):
            widget.textfont(font)
            widget.textsize(text_size)


def run_artifact_browser(
    *,
    data_dir: Path = DEFAULT_UI_DATA_PATH,
    initial_run_id: str | None = None,
) -> None:
    apply_default_ui_font_defaults(fltk)
    browser = ArtifactBrowserWindow(
        data_dir=data_dir,
        initial_run_id=initial_run_id,
    )
    browser.show()
    _run_browser_event_loop(close_browser=browser.close_browser)

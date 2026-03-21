from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import fltk
except ModuleNotFoundError:  # pragma: no cover - depends on optional GUI extra
    fltk = None

from xs2n.ui.fltk_style import apply_widget_theme, style_widget
from xs2n.ui.theme import CLASSIC_LIGHT_THEME, UiTheme, to_fltk_color

if TYPE_CHECKING:
    from xs2n.schemas.auth import AuthDoctorResult


AUTH_WINDOW_WIDTH = 720
AUTH_WINDOW_HEIGHT = 300
WINDOW_PADDING = 12
SECTION_GAP = 16
SECTION_HEADER_HEIGHT = 24
STATUS_HEIGHT = 74
ROW_HEIGHT = 28
BUTTON_WIDTH = 92
BUTTON_GAP = 8


class AuthWindow:
    def __init__(
        self,
        *,
        on_action_requested: Callable[[str], None] | None = None,
    ) -> None:
        if fltk is None:
            raise RuntimeError("pyfltk is required to create the authentication window.")

        self.on_action_requested = on_action_requested
        self.action_buttons: list[object] = []
        self.window = fltk.Fl_Double_Window(
            AUTH_WINDOW_WIDTH,
            AUTH_WINDOW_HEIGHT,
            "Authentication",
        )
        self._build_window()
        self.apply_theme(CLASSIC_LIGHT_THEME)

    def show(self) -> None:
        self.window.show()

    def hide(self) -> None:
        self.window.hide()

    def update_snapshot(
        self,
        *,
        snapshot: object,
        cookies_file: Path,
    ) -> None:
        self.codex_status_output.value(self._format_provider_status(snapshot.codex))
        self.x_status_output.value(self._format_provider_status(snapshot.x))
        self.x_cookies_path_output.value(str(cookies_file))

    def _build_window(self) -> None:
        self.window.begin()
        style_widget(self.window, label_size=14)

        content_width = AUTH_WINDOW_WIDTH - (WINDOW_PADDING * 2)
        section_width = (content_width - SECTION_GAP) // 2
        left_x = WINDOW_PADDING
        right_x = left_x + section_width + SECTION_GAP
        section_y = WINDOW_PADDING

        self._build_codex_section(x=left_x, y=section_y, width=section_width)
        self._build_x_section(x=right_x, y=section_y, width=section_width)

        self.window.end()
        self.window.callback(lambda *_args: self.hide())

    def _build_codex_section(self, *, x: int, y: int, width: int) -> None:
        self.codex_header = fltk.Fl_Box(x, y, width, SECTION_HEADER_HEIGHT, "Codex")
        self.codex_header.box(fltk.FL_THIN_UP_BOX)
        style_widget(self.codex_header, label_size=12, bold=True)

        self.codex_status_output = fltk.Fl_Multiline_Output(
            x,
            y + SECTION_HEADER_HEIGHT + 6,
            width,
            STATUS_HEIGHT,
            "",
        )
        style_widget(self.codex_status_output, text_size=12)

        row_y = y + SECTION_HEADER_HEIGHT + 6 + STATUS_HEIGHT + 8
        refresh_button = self._create_button(
            x=x,
            y=row_y,
            width=BUTTON_WIDTH,
            label="Refresh",
            action="refresh",
        )
        login_button = self._create_button(
            x=x + BUTTON_WIDTH + BUTTON_GAP,
            y=row_y,
            width=BUTTON_WIDTH,
            label="Login",
            action="codex_login",
        )
        logout_button = self._create_button(
            x=x + ((BUTTON_WIDTH + BUTTON_GAP) * 2),
            y=row_y,
            width=BUTTON_WIDTH,
            label="Logout",
            action="codex_logout",
        )
        for widget in (refresh_button, login_button, logout_button):
            widget.align(fltk.FL_ALIGN_CENTER)

    def _build_x_section(self, *, x: int, y: int, width: int) -> None:
        self.x_header = fltk.Fl_Box(x, y, width, SECTION_HEADER_HEIGHT, "X / Twitter")
        self.x_header.box(fltk.FL_THIN_UP_BOX)
        style_widget(self.x_header, label_size=12, bold=True)

        self.x_status_output = fltk.Fl_Multiline_Output(
            x,
            y + SECTION_HEADER_HEIGHT + 6,
            width,
            STATUS_HEIGHT,
            "",
        )
        style_widget(self.x_status_output, text_size=12)

        path_y = y + SECTION_HEADER_HEIGHT + 6 + STATUS_HEIGHT + 8
        self.path_label = fltk.Fl_Box(x, path_y, 72, ROW_HEIGHT, "Cookies")
        self.path_label.align(fltk.FL_ALIGN_LEFT | fltk.FL_ALIGN_INSIDE)
        style_widget(self.path_label, label_size=12, bold=True)

        self.x_cookies_path_output = fltk.Fl_Output(
            x + 72,
            path_y,
            width - 72,
            ROW_HEIGHT,
            "",
        )
        style_widget(self.x_cookies_path_output, text_size=12)

        button_y = path_y + ROW_HEIGHT + 8
        refresh_button = self._create_button(
            x=x,
            y=button_y,
            width=BUTTON_WIDTH,
            label="Refresh",
            action="refresh",
        )
        login_button = self._create_button(
            x=x + BUTTON_WIDTH + BUTTON_GAP,
            y=button_y,
            width=BUTTON_WIDTH,
            label="Login",
            action="x_login",
        )
        reset_button = self._create_button(
            x=x + ((BUTTON_WIDTH + BUTTON_GAP) * 2),
            y=button_y,
            width=BUTTON_WIDTH,
            label="Reset",
            action="x_reset",
        )
        for widget in (refresh_button, login_button, reset_button):
            widget.align(fltk.FL_ALIGN_CENTER)

    def _create_button(
        self,
        *,
        x: int,
        y: int,
        width: int,
        label: str,
        action: str,
    ):
        button = fltk.Fl_Button(x, y, width, ROW_HEIGHT, label)
        style_widget(button, label_size=12)
        button.callback(lambda *_args, action=action: self._dispatch_action(action), None)
        self.action_buttons.append(button)
        return button

    def _dispatch_action(self, action: str) -> None:
        if self.on_action_requested is not None:
            self.on_action_requested(action)

    def _on_refresh_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        self._dispatch_action("refresh")

    def _on_codex_login_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        self._dispatch_action("codex_login")

    def _on_codex_logout_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        self._dispatch_action("codex_logout")

    def _on_x_login_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        self._dispatch_action("x_login")

    def _on_x_reset_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        self._dispatch_action("x_reset")

    @staticmethod
    def _format_provider_status(status: object) -> str:
        lines: list[str] = []
        summary = getattr(status, "summary", None)
        detail = getattr(status, "detail", None)
        if summary:
            lines.append(summary)
        if detail:
            lines.append(detail)
        return "\n".join(lines)

    def apply_theme(self, theme: UiTheme) -> None:
        if fltk is None:
            return

        window_color = to_fltk_color(fltk, theme.window_bg)
        panel_color = to_fltk_color(fltk, theme.header_bg)
        panel_bg2_color = to_fltk_color(fltk, theme.panel_bg2)
        text_color = to_fltk_color(fltk, theme.text)
        selection_color = to_fltk_color(fltk, theme.selection_bg)
        pressed_color = to_fltk_color(fltk, theme.control_pressed_bg)

        apply_widget_theme((self.window,), color=window_color)
        apply_widget_theme(
            (self.codex_header, self.x_header),
            color=panel_color,
            label_color=text_color,
        )
        apply_widget_theme(
            (self.path_label,),
            color=window_color,
            label_color=text_color,
        )
        apply_widget_theme(
            (
                self.codex_status_output,
                self.x_status_output,
                self.x_cookies_path_output,
            ),
            color=panel_bg2_color,
            text_color=text_color,
            label_color=text_color,
        )
        apply_widget_theme(
            self.action_buttons,
            color=panel_color,
            selection_color=pressed_color,
            label_color=text_color,
        )

        self.window.redraw()

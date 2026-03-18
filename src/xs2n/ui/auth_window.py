from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import fltk
except ModuleNotFoundError:  # pragma: no cover - depends on optional GUI extra
    fltk = None

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
        self.window = fltk.Fl_Double_Window(
            AUTH_WINDOW_WIDTH,
            AUTH_WINDOW_HEIGHT,
            "Authentication",
        )
        self._build_window()

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
        self._style_widget(self.window, label_size=14)

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
        header = fltk.Fl_Box(x, y, width, SECTION_HEADER_HEIGHT, "Codex")
        header.box(fltk.FL_THIN_UP_BOX)
        self._style_widget(header, label_size=12, bold=True)

        self.codex_status_output = fltk.Fl_Multiline_Output(
            x,
            y + SECTION_HEADER_HEIGHT + 6,
            width,
            STATUS_HEIGHT,
            "",
        )
        self._style_widget(self.codex_status_output, text_size=12)

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
        header = fltk.Fl_Box(x, y, width, SECTION_HEADER_HEIGHT, "X / Twitter")
        header.box(fltk.FL_THIN_UP_BOX)
        self._style_widget(header, label_size=12, bold=True)

        self.x_status_output = fltk.Fl_Multiline_Output(
            x,
            y + SECTION_HEADER_HEIGHT + 6,
            width,
            STATUS_HEIGHT,
            "",
        )
        self._style_widget(self.x_status_output, text_size=12)

        path_y = y + SECTION_HEADER_HEIGHT + 6 + STATUS_HEIGHT + 8
        path_label = fltk.Fl_Box(x, path_y, 72, ROW_HEIGHT, "Cookies")
        path_label.align(fltk.FL_ALIGN_LEFT | fltk.FL_ALIGN_INSIDE)
        self._style_widget(path_label, label_size=12, bold=True)

        self.x_cookies_path_output = fltk.Fl_Output(
            x + 72,
            path_y,
            width - 72,
            ROW_HEIGHT,
            "",
        )
        self._style_widget(self.x_cookies_path_output, text_size=12)

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
        self._style_widget(button, label_size=12)
        button.callback(lambda *_args, action=action: self._dispatch_action(action), None)
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

    @staticmethod
    def _style_widget(widget, *, label_size: int | None = None, text_size: int | None = None, bold: bool = False) -> None:  # noqa: ANN001
        if label_size is not None:
            widget.labelsize(label_size)
        if text_size is not None and hasattr(widget, "textsize"):
            widget.textsize(text_size)
        if bold and hasattr(widget, "labelfont"):
            widget.labelfont(fltk.FL_HELVETICA_BOLD)

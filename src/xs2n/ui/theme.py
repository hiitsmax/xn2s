from __future__ import annotations

from dataclasses import dataclass
import subprocess
import sys
from typing import Literal


AppearanceMode = Literal["system", "classic_light", "classic_dark"]
VALID_APPEARANCE_MODES = {"system", "classic_light", "classic_dark"}
APPEARANCE_MODE_OPTIONS: tuple[tuple[str, AppearanceMode], ...] = (
    ("System", "system"),
    ("Classic Light", "classic_light"),
    ("Classic Dark", "classic_dark"),
)


@dataclass(frozen=True, slots=True)
class UiTheme:
    name: str
    window_bg: str
    panel_bg: str
    panel_bg2: str
    control_bg: str
    control_pressed_bg: str
    header_bg: str
    header_cell_bg: str
    viewer_bg: str
    viewer_panel_bg: str
    viewer_plain_bg: str
    text: str
    muted_text: str
    selection_bg: str
    selection_text: str
    tooltip_bg: str
    tooltip_text: str


CLASSIC_LIGHT_THEME = UiTheme(
    name="classic_light",
    window_bg="#C0C0C0",
    panel_bg="#D4D0C8",
    panel_bg2="#FFFFFF",
    control_bg="#D4D0C8",
    control_pressed_bg="#B5B5AE",
    header_bg="#D0CCC2",
    header_cell_bg="#DFDCD5",
    viewer_bg="#ECE8DC",
    viewer_panel_bg="#CFC8B6",
    viewer_plain_bg="#F6F4ED",
    text="#202020",
    muted_text="#5E5A52",
    selection_bg="#000080",
    selection_text="#FFFFFF",
    tooltip_bg="#FFFFE1",
    tooltip_text="#000000",
)

CLASSIC_DARK_THEME = UiTheme(
    name="classic_dark",
    window_bg="#3B3833",
    panel_bg="#4A463F",
    panel_bg2="#26241F",
    control_bg="#26241F",
    control_pressed_bg="#171612",
    header_bg="#4A463F",
    header_cell_bg="#555046",
    viewer_bg="#1F1D19",
    viewer_panel_bg="#4A463F",
    viewer_plain_bg="#26241F",
    text="#DDD7C8",
    muted_text="#A8A08F",
    selection_bg="#4E6E92",
    selection_text="#F5F1E6",
    tooltip_bg="#4A463F",
    tooltip_text="#F5F1E6",
)


def normalize_appearance_mode(value: str | None) -> AppearanceMode:
    normalized = (value or "").strip().lower()
    if normalized in VALID_APPEARANCE_MODES:
        return normalized  # type: ignore[return-value]
    return "system"


def resolve_ui_theme(
    mode: str | None,
    *,
    platform: str = sys.platform,
    subprocess_run=subprocess.run,
    winreg_module=None,
) -> UiTheme:
    normalized = normalize_appearance_mode(mode)
    if normalized == "classic_dark":
        return CLASSIC_DARK_THEME
    if normalized == "classic_light":
        return CLASSIC_LIGHT_THEME
    if _detect_system_dark_mode(
        platform=platform,
        subprocess_run=subprocess_run,
        winreg_module=winreg_module,
    ):
        return CLASSIC_DARK_THEME
    return CLASSIC_LIGHT_THEME


def apply_fltk_theme_defaults(fltk_module, theme: UiTheme) -> None:  # noqa: ANN001
    fl_namespace = getattr(fltk_module, "Fl", None)
    if fl_namespace is None:
        return

    if hasattr(fl_namespace, "background"):
        fl_namespace.background(*hex_to_rgb(theme.window_bg))
    if hasattr(fl_namespace, "background2"):
        fl_namespace.background2(*hex_to_rgb(theme.panel_bg2))
    if hasattr(fl_namespace, "foreground"):
        fl_namespace.foreground(*hex_to_rgb(theme.text))
    if hasattr(fl_namespace, "set_color"):
        if hasattr(fltk_module, "FL_SELECTION_COLOR"):
            fl_namespace.set_color(
                fltk_module.FL_SELECTION_COLOR,
                *hex_to_rgb(theme.selection_bg),
            )
        if hasattr(fltk_module, "FL_INACTIVE_COLOR"):
            fl_namespace.set_color(
                fltk_module.FL_INACTIVE_COLOR,
                *hex_to_rgb(theme.muted_text),
            )


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    normalized = value.removeprefix("#")
    if len(normalized) != 6:
        raise ValueError(f"Expected a 6-digit hex color, got {value!r}.")
    return (
        int(normalized[0:2], 16),
        int(normalized[2:4], 16),
        int(normalized[4:6], 16),
    )


def to_fltk_color(fltk_module, value: str) -> int:  # noqa: ANN001
    return fltk_module.fl_rgb_color(*hex_to_rgb(value))


def _detect_system_dark_mode(
    *,
    platform: str,
    subprocess_run,
    winreg_module,
) -> bool:
    if platform == "darwin":
        return _detect_macos_dark_mode(subprocess_run)
    if platform == "win32":
        return _detect_windows_dark_mode(winreg_module)
    return False


def _detect_macos_dark_mode(subprocess_run) -> bool:  # noqa: ANN001
    try:
        completed = subprocess_run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return False
    return (
        completed.returncode == 0
        and completed.stdout.strip().lower() == "dark"
    )


def _detect_windows_dark_mode(winreg_module) -> bool:  # noqa: ANN001
    if winreg_module is None:
        try:
            import winreg as imported_winreg
        except ImportError:
            return False
        winreg_module = imported_winreg

    try:
        with winreg_module.OpenKey(  # type: ignore[attr-defined]
            winreg_module.HKEY_CURRENT_USER,  # type: ignore[attr-defined]
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as registry_key:
            apps_use_light_theme, _value_type = winreg_module.QueryValueEx(
                registry_key,
                "AppsUseLightTheme",
            )
    except OSError:
        return False
    return int(apps_use_light_theme) == 0

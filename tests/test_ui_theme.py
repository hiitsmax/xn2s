from __future__ import annotations

from types import SimpleNamespace

from xs2n.ui.theme import (
    CLASSIC_DARK_THEME,
    CLASSIC_LIGHT_THEME,
    apply_fltk_theme_defaults,
    normalize_appearance_mode,
    resolve_ui_theme,
)


def test_normalize_appearance_mode_defaults_to_system() -> None:
    assert normalize_appearance_mode(None) == "system"
    assert normalize_appearance_mode("") == "system"
    assert normalize_appearance_mode(" CLASSIC_DARK ") == "classic_dark"
    assert normalize_appearance_mode("unknown") == "system"


def test_resolve_ui_theme_keeps_explicit_override() -> None:
    assert resolve_ui_theme("classic_light") == CLASSIC_LIGHT_THEME
    assert resolve_ui_theme("classic_dark") == CLASSIC_DARK_THEME


def test_resolve_ui_theme_uses_system_dark_on_macos() -> None:
    def fake_run(command, *, capture_output, check, text):  # noqa: ANN001
        assert command == ["defaults", "read", "-g", "AppleInterfaceStyle"]
        assert capture_output is True
        assert check is False
        assert text is True
        return SimpleNamespace(returncode=0, stdout="Dark\n")

    assert (
        resolve_ui_theme(
            "system",
            platform="darwin",
            subprocess_run=fake_run,
        )
        == CLASSIC_DARK_THEME
    )


def test_apply_fltk_theme_defaults_updates_global_palette() -> None:
    calls: list[tuple[str, object]] = []

    class FakeFl:
        @staticmethod
        def background(r: int, g: int, b: int) -> None:
            calls.append(("background", (r, g, b)))

        @staticmethod
        def background2(r: int, g: int, b: int) -> None:
            calls.append(("background2", (r, g, b)))

        @staticmethod
        def foreground(r: int, g: int, b: int) -> None:
            calls.append(("foreground", (r, g, b)))

        @staticmethod
        def set_color(index: int, r: int, g: int, b: int) -> None:
            calls.append(("set_color", (index, r, g, b)))

    fake_fltk = SimpleNamespace(
        Fl=FakeFl,
        FL_SELECTION_COLOR=15,
        FL_INACTIVE_COLOR=8,
    )

    apply_fltk_theme_defaults(fake_fltk, CLASSIC_DARK_THEME)

    assert ("background", (59, 56, 51)) in calls
    assert ("background2", (38, 36, 31)) in calls
    assert ("foreground", (221, 215, 200)) in calls
    assert ("set_color", (15, 78, 110, 146)) in calls
    assert ("set_color", (8, 168, 160, 143)) in calls

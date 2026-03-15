from __future__ import annotations

import sys

import pytest

from xs2n.ui.macos.app_menu import (
    APP_NAME,
    apply_macos_app_menu,
    build_app_menu_spec,
    prepare_macos_app_menu,
)


def test_build_app_menu_spec_contains_only_about_and_quit() -> None:
    spec = build_app_menu_spec()

    assert spec.app_name == APP_NAME
    assert [item.title for item in spec.items] == [
        "About xn2s",
        "Quit xn2s",
    ]
    assert [item.action for item in spec.items] == [
        "orderFrontStandardAboutPanel:",
        "terminate:",
    ]
    assert [item.key_equivalent for item in spec.items] == [
        "",
        "q",
    ]


def test_apply_macos_app_menu_skips_non_macos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("xs2n.ui.macos.app_menu.sys.platform", "linux")
    monkeypatch.setattr(
        "xs2n.ui.macos.app_menu._install_macos_app_menu",
        lambda spec: (_ for _ in ()).throw(AssertionError("should not run")),
    )

    assert apply_macos_app_menu() is False


def test_apply_macos_app_menu_builds_spec_for_installer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_install(spec) -> None:
        captured["spec"] = spec

    monkeypatch.setattr("xs2n.ui.macos.app_menu.sys.platform", "darwin")
    monkeypatch.setattr(
        "xs2n.ui.macos.app_menu._install_macos_app_menu",
        fake_install,
    )

    assert apply_macos_app_menu() is True
    spec = captured["spec"]
    assert spec.app_name == APP_NAME
    assert [item.title for item in spec.items] == [
        "About xn2s",
        "Quit xn2s",
    ]


def test_prepare_macos_app_menu_uses_fltk_window_menu_style(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSysMenuBar:
        no_window_menu = "no-window"

        @staticmethod
        def window_menu_style(style) -> None:
            captured["style"] = style

    class FakeFltk:
        Fl_Sys_Menu_Bar = FakeSysMenuBar

    captured: dict[str, object] = {}

    monkeypatch.setattr("xs2n.ui.macos.app_menu.sys.platform", "darwin")
    monkeypatch.setitem(sys.modules, "fltk", FakeFltk)

    assert prepare_macos_app_menu() is True
    assert captured == {"style": "no-window"}

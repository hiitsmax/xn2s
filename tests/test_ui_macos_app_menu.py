from __future__ import annotations

import sys

import pytest

from xs2n.ui.macos.app_menu import (
    ABOUT_PANEL_MESSAGE,
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
        "showAboutPanel:",
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


def test_show_about_alert_uses_custom_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from xs2n.ui.macos import app_menu

    captured: dict[str, list[tuple[object, ...]]] = {}

    class FakeBridge:
        def get_class(self, name: str):
            return f"class:{name}"

        def send_id(self, receiver, selector: str):
            captured.setdefault("send_id", []).append((receiver, selector))
            return f"{receiver}:{selector}"

        def send_void_id(self, receiver, selector: str, argument):
            captured.setdefault("send_void_id", []).append(
                (receiver, selector, argument)
            )

        def send_void(self, receiver, selector: str):
            captured.setdefault("send_void", []).append((receiver, selector))

        def send_id_id(self, receiver, selector: str, argument):
            captured.setdefault("send_id_id", []).append(
                (receiver, selector, argument)
            )
            return f"{receiver}:{selector}:{argument}"

        def nsstring(self, value: str):
            return f"ns:{value}"

    monkeypatch.setattr(app_menu, "_ObjectiveCBridge", FakeBridge)

    app_menu._show_about_alert()

    assert ("class:NSAlert", "alloc") in captured["send_id"]
    assert (
        "class:NSAlert:alloc:init",
        "setMessageText:",
        "ns:xn2s",
    ) in captured["send_void_id"]
    assert (
        "class:NSAlert:alloc:init",
        "setInformativeText:",
        f"ns:{ABOUT_PANEL_MESSAGE}",
    ) in captured["send_void_id"]
    assert captured["send_void"] == [
        ("class:NSAlert:alloc:init", "runModal")
    ]

from __future__ import annotations

import ctypes
from ctypes import c_char_p, c_long, c_void_p
from ctypes.util import find_library
from dataclasses import dataclass
import sys


APP_NAME = "xn2s"


@dataclass(frozen=True, slots=True)
class AppMenuItem:
    title: str
    action: str
    key_equivalent: str = ""


@dataclass(frozen=True, slots=True)
class AppMenuSpec:
    app_name: str
    items: tuple[AppMenuItem, ...]


def build_app_menu_spec(app_name: str = APP_NAME) -> AppMenuSpec:
    return AppMenuSpec(
        app_name=app_name,
        items=(
            AppMenuItem(
                title=f"About {app_name}",
                action="orderFrontStandardAboutPanel:",
            ),
            AppMenuItem(
                title=f"Quit {app_name}",
                action="terminate:",
                key_equivalent="q",
            ),
        ),
    )


def apply_macos_app_menu(app_name: str = APP_NAME) -> bool:
    if sys.platform != "darwin":
        return False

    spec = build_app_menu_spec(app_name)
    try:
        _install_macos_app_menu(spec)
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def prepare_macos_app_menu() -> bool:
    if sys.platform != "darwin":
        return False

    try:
        import fltk

        fltk.Fl_Sys_Menu_Bar.window_menu_style(
            fltk.Fl_Sys_Menu_Bar.no_window_menu
        )
    except (AttributeError, RuntimeError):
        return False
    return True


class _ObjectiveCBridge:
    def __init__(self) -> None:
        objc_path = find_library("objc")
        appkit_path = find_library("AppKit")
        foundation_path = find_library("Foundation")
        if not objc_path or not appkit_path or not foundation_path:
            raise RuntimeError("macOS Objective-C runtime libraries not found")

        self._objc = ctypes.CDLL(objc_path)
        ctypes.CDLL(appkit_path)
        ctypes.CDLL(foundation_path)

        self._objc.objc_getClass.argtypes = [c_char_p]
        self._objc.objc_getClass.restype = c_void_p
        self._objc.sel_registerName.argtypes = [c_char_p]
        self._objc.sel_registerName.restype = c_void_p

        self._send_id = ctypes.CFUNCTYPE(c_void_p, c_void_p, c_void_p)(
            ("objc_msgSend", self._objc)
        )
        self._send_id_cchar = ctypes.CFUNCTYPE(
            c_void_p, c_void_p, c_void_p, c_char_p
        )(("objc_msgSend", self._objc))
        self._send_id_id = ctypes.CFUNCTYPE(
            c_void_p, c_void_p, c_void_p, c_void_p
        )(("objc_msgSend", self._objc))
        self._send_void_id = ctypes.CFUNCTYPE(
            None, c_void_p, c_void_p, c_void_p
        )(("objc_msgSend", self._objc))
        self._send_void_long = ctypes.CFUNCTYPE(
            None, c_void_p, c_void_p, c_long
        )(("objc_msgSend", self._objc))
        self._send_long = ctypes.CFUNCTYPE(c_long, c_void_p, c_void_p)(
            ("objc_msgSend", self._objc)
        )
        self._send_id_id_sel_id = ctypes.CFUNCTYPE(
            c_void_p,
            c_void_p,
            c_void_p,
            c_void_p,
            c_void_p,
            c_void_p,
        )(("objc_msgSend", self._objc))

    def get_class(self, name: str) -> c_void_p:
        class_ref = self._objc.objc_getClass(name.encode("utf-8"))
        if not class_ref:
            raise RuntimeError(f"Objective-C class not found: {name}")
        return class_ref

    def get_selector(self, name: str) -> c_void_p:
        selector = self._objc.sel_registerName(name.encode("utf-8"))
        if not selector:
            raise RuntimeError(f"Objective-C selector not found: {name}")
        return selector

    def send_id(self, receiver: c_void_p, selector: str) -> c_void_p:
        return self._send_id(receiver, self.get_selector(selector))

    def send_id_cchar(
        self,
        receiver: c_void_p,
        selector: str,
        value: str,
    ) -> c_void_p:
        return self._send_id_cchar(
            receiver,
            self.get_selector(selector),
            value.encode("utf-8"),
        )

    def send_id_id(
        self,
        receiver: c_void_p,
        selector: str,
        argument: c_void_p,
    ) -> c_void_p:
        return self._send_id_id(receiver, self.get_selector(selector), argument)

    def send_void_id(
        self,
        receiver: c_void_p,
        selector: str,
        argument: c_void_p,
    ) -> None:
        self._send_void_id(receiver, self.get_selector(selector), argument)

    def send_void_long(
        self,
        receiver: c_void_p,
        selector: str,
        argument: int,
    ) -> None:
        self._send_void_long(receiver, self.get_selector(selector), argument)

    def send_long(self, receiver: c_void_p, selector: str) -> int:
        return int(self._send_long(receiver, self.get_selector(selector)))

    def send_id_id_sel_id(
        self,
        receiver: c_void_p,
        selector: str,
        arg1: c_void_p,
        arg2: c_void_p,
        arg3: c_void_p,
    ) -> c_void_p:
        return self._send_id_id_sel_id(
            receiver,
            self.get_selector(selector),
            arg1,
            arg2,
            arg3,
        )

    def nsstring(self, value: str) -> c_void_p:
        string_class = self.get_class("NSString")
        allocated = self.send_id(string_class, "alloc")
        return self.send_id_cchar(allocated, "initWithUTF8String:", value)


def _install_macos_app_menu(spec: AppMenuSpec) -> None:
    bridge = _ObjectiveCBridge()
    app = bridge.send_id(bridge.get_class("NSApplication"), "sharedApplication")
    process_info = bridge.send_id(
        bridge.get_class("NSProcessInfo"),
        "processInfo",
    )
    bridge.send_void_id(
        process_info,
        "setProcessName:",
        bridge.nsstring(spec.app_name),
    )

    main_menu = bridge.send_id(app, "mainMenu")
    if not main_menu:
        main_menu = _create_menu(bridge, "Main")

    _clear_menu(bridge, main_menu)

    app_menu_item = _create_menu_item(
        bridge,
        title=spec.app_name,
        action=None,
        key_equivalent="",
        target=None,
    )
    app_submenu = _create_menu(bridge, spec.app_name)

    for item in spec.items:
        menu_item = _create_menu_item(
            bridge,
            title=item.title,
            action=item.action,
            key_equivalent=item.key_equivalent,
            target=app,
        )
        bridge.send_id_id(app_submenu, "addItem:", menu_item)

    bridge.send_void_id(app_menu_item, "setSubmenu:", app_submenu)
    bridge.send_id_id(main_menu, "addItem:", app_menu_item)
    bridge.send_void_id(app, "setMainMenu:", main_menu)


def _create_menu(bridge: _ObjectiveCBridge, title: str) -> c_void_p:
    menu_class = bridge.get_class("NSMenu")
    allocated = bridge.send_id(menu_class, "alloc")
    return bridge.send_id_id(allocated, "initWithTitle:", bridge.nsstring(title))


def _create_menu_item(
    bridge: _ObjectiveCBridge,
    *,
    title: str,
    action: str | None,
    key_equivalent: str,
    target: c_void_p | None,
) -> c_void_p:
    menu_item_class = bridge.get_class("NSMenuItem")
    allocated = bridge.send_id(menu_item_class, "alloc")
    action_selector = c_void_p(0)
    if action is not None:
        action_selector = bridge.get_selector(action)
    item = bridge.send_id_id_sel_id(
        allocated,
        "initWithTitle:action:keyEquivalent:",
        bridge.nsstring(title),
        action_selector,
        bridge.nsstring(key_equivalent),
    )
    if target is not None:
        bridge.send_void_id(item, "setTarget:", target)
    return item


def _clear_menu(bridge: _ObjectiveCBridge, menu: c_void_p) -> None:
    count = bridge.send_long(menu, "numberOfItems")
    for index in range(count - 1, -1, -1):
        bridge.send_void_long(menu, "removeItemAtIndex:", index)

from __future__ import annotations

import ctypes
from ctypes import CFUNCTYPE, c_char_p, c_long, c_void_p
from ctypes.util import find_library
from dataclasses import dataclass
import sys


APP_NAME = "xn2s"
ABOUT_PANEL_MESSAGE = "x noise 2 signal\nNative artifact browser for digest runs."


@dataclass(frozen=True, slots=True)
class AppMenuItem:
    title: str
    action: str
    key_equivalent: str = ""
    target_kind: str = "application"


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
                action="showAboutPanel:",
                target_kind="about_target",
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

    try:
        _install_macos_app_menu(build_app_menu_spec(app_name))
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
        self._send_void = ctypes.CFUNCTYPE(None, c_void_p, c_void_p)(
            ("objc_msgSend", self._objc)
        )

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

    def send_void(self, receiver: c_void_p, selector: str) -> None:
        self._send_void(receiver, self.get_selector(selector))

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
    main_menu = bridge.send_id(app, "mainMenu")
    if not main_menu:
        main_menu = _create_menu(bridge, "Main")

    _clear_menu(bridge, main_menu)
    about_target = _get_about_menu_target()

    app_menu_item = _create_menu_item(
        bridge,
        title=spec.app_name,
        action=None,
        key_equivalent="",
        target=None,
    )
    app_submenu = _create_menu(bridge, spec.app_name)

    for item in spec.items:
        target = app if item.target_kind == "application" else about_target
        menu_item = _create_menu_item(
            bridge,
            title=item.title,
            action=item.action,
            key_equivalent=item.key_equivalent,
            target=target,
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


_ABOUT_TARGET_CLASS_NAME = "Xn2sAboutMenuTarget"
_ABOUT_TARGET_INSTANCE: c_void_p | None = None
_ABOUT_TARGET_IMP = None


def _get_about_menu_target() -> c_void_p:
    global _ABOUT_TARGET_INSTANCE
    if _ABOUT_TARGET_INSTANCE is not None:
        return _ABOUT_TARGET_INSTANCE

    bridge = _ObjectiveCBridge()
    target_class = _get_or_create_about_target_class(bridge)
    allocated = bridge.send_id(target_class, "alloc")
    _ABOUT_TARGET_INSTANCE = bridge.send_id(allocated, "init")
    if not _ABOUT_TARGET_INSTANCE:
        raise RuntimeError("Failed to initialize about target")
    return _ABOUT_TARGET_INSTANCE


def _get_or_create_about_target_class(bridge: _ObjectiveCBridge) -> c_void_p:
    existing_class = bridge._objc.objc_getClass(
        _ABOUT_TARGET_CLASS_NAME.encode("utf-8")
    )
    if existing_class:
        return existing_class

    allocate_class_pair = bridge._objc.objc_allocateClassPair
    allocate_class_pair.argtypes = [c_void_p, c_char_p, ctypes.c_size_t]
    allocate_class_pair.restype = c_void_p

    class_add_method = bridge._objc.class_addMethod
    class_add_method.argtypes = [c_void_p, c_void_p, c_void_p, c_char_p]
    class_add_method.restype = ctypes.c_bool

    register_class_pair = bridge._objc.objc_registerClassPair
    register_class_pair.argtypes = [c_void_p]
    register_class_pair.restype = None

    target_class = allocate_class_pair(
        bridge.get_class("NSObject"),
        _ABOUT_TARGET_CLASS_NAME.encode("utf-8"),
        0,
    )
    if not target_class:
        raise RuntimeError("Failed to allocate About target class")

    about_callback = _build_about_callback()
    added = class_add_method(
        target_class,
        bridge.get_selector("showAboutPanel:"),
        ctypes.cast(about_callback, c_void_p),
        b"v@:@",
    )
    if not added:
        raise RuntimeError("Failed to add showAboutPanel: method")

    register_class_pair(target_class)
    return target_class


def _build_about_callback():
    global _ABOUT_TARGET_IMP
    if _ABOUT_TARGET_IMP is not None:
        return _ABOUT_TARGET_IMP

    @CFUNCTYPE(None, c_void_p, c_void_p, c_void_p)
    def show_about_panel(_self, _cmd, _sender) -> None:
        _show_about_alert()

    _ABOUT_TARGET_IMP = show_about_panel
    return _ABOUT_TARGET_IMP


def _show_about_alert() -> None:
    bridge = _ObjectiveCBridge()
    alert = bridge.send_id(bridge.get_class("NSAlert"), "alloc")
    alert = bridge.send_id(alert, "init")
    bridge.send_void_id(alert, "setMessageText:", bridge.nsstring(APP_NAME))
    bridge.send_void_id(
        alert,
        "setInformativeText:",
        bridge.nsstring(ABOUT_PANEL_MESSAGE),
    )
    bridge.send_id_id(
        alert,
        "addButtonWithTitle:",
        bridge.nsstring("OK"),
    )
    bridge.send_void(alert, "runModal")

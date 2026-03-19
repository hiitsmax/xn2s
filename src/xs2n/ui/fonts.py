from __future__ import annotations

import sys
from typing import Any


DEFAULT_UI_FONT_FAMILY = "Microsoft Sans Serif"
DEFAULT_UI_HTML_FONT_FAMILY = (
    "Helvetica"
    if sys.platform == "darwin"
    else DEFAULT_UI_FONT_FAMILY
)

_DEFAULT_UI_FONT_VARIANTS = (
    ("FL_HELVETICA", 0, ("Microsoft Sans Serif", "Tahoma")),
    ("FL_HELVETICA_BOLD", 1, ("Tahoma Bold", "Tahoma", "Microsoft Sans Serif")),
    ("FL_HELVETICA_ITALIC", 2, ("Tahoma", "Microsoft Sans Serif")),
    ("FL_HELVETICA_BOLD_ITALIC", 3, ("Tahoma Bold", "Tahoma", "Microsoft Sans Serif")),
)


def apply_default_ui_font_defaults(fltk_module: Any) -> None:
    fl_namespace = getattr(fltk_module, "Fl", None)
    if fl_namespace is None:
        return
    if not hasattr(fl_namespace, "set_fonts") or not hasattr(
        fl_namespace, "set_font"
    ):
        return

    font_count = fl_namespace.set_fonts()
    if not isinstance(font_count, int):
        return

    available_names = _available_font_names(
        fl_namespace=fl_namespace,
        font_count=font_count,
    )
    for constant_name, fallback_index, candidate_names in _DEFAULT_UI_FONT_VARIANTS:
        font_name = _resolve_first_available_font_name(
            candidate_names=candidate_names,
            available_names=available_names,
        )
        if font_name is None:
            continue
        font_index = getattr(fltk_module, constant_name, fallback_index)
        fl_namespace.set_font(font_index, font_name)


def _resolve_first_available_font_name(
    *,
    candidate_names: tuple[str, ...],
    available_names: set[str],
) -> str | None:
    for font_name in candidate_names:
        if font_name in available_names:
            return font_name
    return None


def _available_font_names(*, fl_namespace: Any, font_count: int) -> set[str]:
    if not hasattr(fl_namespace, "get_font_name"):
        return set()

    available_names: set[str] = set()
    for index in range(font_count):
        raw_name = fl_namespace.get_font_name(index)
        font_name = raw_name[0] if isinstance(raw_name, (list, tuple)) else raw_name
        if not isinstance(font_name, str):
            continue
        available_names.add(font_name.strip())
    return available_names

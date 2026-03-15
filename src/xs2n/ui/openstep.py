from __future__ import annotations

from typing import Any


OPENSTEP_FONT_FAMILY = "Helvetica"

_OPENSTEP_FONT_VARIANTS = (
    ("FL_HELVETICA", 0, "Helvetica"),
    ("FL_HELVETICA_BOLD", 1, "Helvetica Bold"),
    ("FL_HELVETICA_ITALIC", 2, "Helvetica Oblique"),
    ("FL_HELVETICA_BOLD_ITALIC", 3, "Helvetica Bold Oblique"),
)


def apply_openstep_font_defaults(fltk_module: Any) -> None:
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
    for constant_name, fallback_index, font_name in _OPENSTEP_FONT_VARIANTS:
        if font_name not in available_names:
            continue
        font_index = getattr(fltk_module, constant_name, fallback_index)
        fl_namespace.set_font(font_index, font_name)


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

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import fltk


def style_widget(
    widget: Any,
    *,
    label_size: int | None = None,
    text_size: int | None = None,
    bold: bool = False,
) -> None:
    font = fltk.FL_HELVETICA_BOLD if bold else fltk.FL_HELVETICA
    if hasattr(widget, "labelfont"):
        widget.labelfont(font)
    if label_size is not None and hasattr(widget, "labelsize"):
        widget.labelsize(label_size)
    if text_size is not None and hasattr(widget, "textfont"):
        widget.textfont(font)
        widget.textsize(text_size)


def apply_widget_theme(
    widgets: Iterable[Any],
    *,
    color: int | None = None,
    selection_color: int | None = None,
    text_color: int | None = None,
    label_color: int | None = None,
) -> None:
    for widget in widgets:
        if color is not None and hasattr(widget, "color"):
            widget.color(color)
        if selection_color is not None and hasattr(widget, "selection_color"):
            widget.selection_color(selection_color)
        if text_color is not None and hasattr(widget, "textcolor"):
            widget.textcolor(text_color)
        if label_color is not None and hasattr(widget, "labelcolor"):
            widget.labelcolor(label_color)

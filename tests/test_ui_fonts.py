from __future__ import annotations

from types import SimpleNamespace

from xs2n.ui.fonts import apply_default_ui_font_defaults


class _FakeFlNamespace:
    def __init__(self, font_names: list[str]) -> None:
        self.font_names = font_names
        self.remapped_fonts: list[tuple[int, str]] = []

    def set_fonts(self) -> int:
        return len(self.font_names)

    def get_font_name(self, index: int) -> list[object]:
        return [self.font_names[index], index]

    def set_font(self, index: int, name: str) -> None:
        self.remapped_fonts.append((index, name))


def test_apply_default_ui_font_defaults_prefers_windows_classic_faces() -> None:
    fake_fl_namespace = _FakeFlNamespace(
        [
            "Arial",
            "Tahoma",
            "Tahoma Bold",
            "Microsoft Sans Serif",
        ]
    )
    fake_fltk = SimpleNamespace(
        Fl=fake_fl_namespace,
        FL_HELVETICA=0,
        FL_HELVETICA_BOLD=1,
        FL_HELVETICA_ITALIC=2,
        FL_HELVETICA_BOLD_ITALIC=3,
    )

    apply_default_ui_font_defaults(fake_fltk)

    assert fake_fl_namespace.remapped_fonts == [
        (0, "Microsoft Sans Serif"),
        (1, "Tahoma Bold"),
        (2, "Tahoma"),
        (3, "Tahoma Bold"),
    ]


def test_apply_default_ui_font_defaults_falls_back_safely() -> None:
    fake_fl_namespace = _FakeFlNamespace(["Arial", "Tahoma"])
    fake_fltk = SimpleNamespace(
        Fl=fake_fl_namespace,
        FL_HELVETICA=0,
        FL_HELVETICA_BOLD=1,
        FL_HELVETICA_ITALIC=2,
        FL_HELVETICA_BOLD_ITALIC=3,
    )

    apply_default_ui_font_defaults(fake_fltk)

    assert fake_fl_namespace.remapped_fonts == [
        (0, "Tahoma"),
        (1, "Tahoma"),
        (2, "Tahoma"),
        (3, "Tahoma"),
    ]

from __future__ import annotations

from types import SimpleNamespace

from xs2n.ui.openstep import apply_openstep_font_defaults


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


def test_apply_openstep_font_defaults_remaps_helvetica_slots() -> None:
    fake_fl_namespace = _FakeFlNamespace(
        [
            "Arial",
            "Arial Bold",
            "Helvetica",
            "Helvetica Bold",
            "Helvetica Oblique",
            "Helvetica Bold Oblique",
        ]
    )
    fake_fltk = SimpleNamespace(
        Fl=fake_fl_namespace,
        FL_HELVETICA=0,
        FL_HELVETICA_BOLD=1,
        FL_HELVETICA_ITALIC=2,
        FL_HELVETICA_BOLD_ITALIC=3,
    )

    apply_openstep_font_defaults(fake_fltk)

    assert fake_fl_namespace.remapped_fonts == [
        (0, "Helvetica"),
        (1, "Helvetica Bold"),
        (2, "Helvetica Oblique"),
        (3, "Helvetica Bold Oblique"),
    ]


def test_apply_openstep_font_defaults_leaves_unknown_fonts_alone() -> None:
    fake_fl_namespace = _FakeFlNamespace(["Arial", "Courier"])
    fake_fltk = SimpleNamespace(
        Fl=fake_fl_namespace,
        FL_HELVETICA=0,
        FL_HELVETICA_BOLD=1,
        FL_HELVETICA_ITALIC=2,
        FL_HELVETICA_BOLD_ITALIC=3,
    )

    apply_openstep_font_defaults(fake_fltk)

    assert fake_fl_namespace.remapped_fonts == []

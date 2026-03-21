from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import fltk

from xs2n.ui.theme import UiTheme, to_fltk_color

CARD_BORDER = 1
CARD_LIST_GAP = 14
CARD_LIST_PADDING = 14
CARD_PADDING_X = 16
CARD_PADDING_Y = 14
CARD_SECTION_GAP = 10
CARD_SOURCE_GAP = 8
CARD_SOURCE_TEXT_INDENT = 14
CARD_BOTTOM_PADDING = 4
TITLE_FONT = fltk.FL_HELVETICA_BOLD
TITLE_SIZE = 18
SUMMARY_FONT = fltk.FL_HELVETICA
SUMMARY_SIZE = 15
SOURCE_META_FONT = fltk.FL_HELVETICA_BOLD
SOURCE_META_SIZE = 11
SOURCE_TEXT_FONT = fltk.FL_HELVETICA
SOURCE_TEXT_SIZE = 14
WHY_LABEL_FONT = fltk.FL_HELVETICA_ITALIC
WHY_LABEL_SIZE = 12
WHY_TEXT_FONT = fltk.FL_HELVETICA
WHY_TEXT_SIZE = 14


@dataclass(slots=True)
class DigestSourcePostWidgets:
    meta_box: Any
    text_box: Any


@dataclass(slots=True)
class DigestThreadCardWidgets:
    group: Any
    surface: Any
    title_box: Any
    summary_box: Any
    source_posts: list[DigestSourcePostWidgets]
    why_label_box: Any
    why_text_box: Any


def build_digest_thread_card(
    *,
    parent,
    x: int,
    y: int,
    width: int,
    thread_index: int,
    thread_card,
    theme: UiTheme,
) -> DigestThreadCardWidgets:
    group = fltk.Fl_Group(x, y, width, 1)
    parent.add(group)
    group.begin()
    surface = fltk.Fl_Box(x, y, width, 1, "")
    title_box = fltk.Fl_Box(x, y, width, 1, "")
    summary_box = fltk.Fl_Box(x, y, width, 1, "")
    source_posts: list[DigestSourcePostWidgets] = []
    for _tweet_index, _tweet in enumerate(thread_card.tweets, start=1):
        source_posts.append(
            DigestSourcePostWidgets(
                meta_box=fltk.Fl_Box(x, y, width, 1, ""),
                text_box=fltk.Fl_Box(x, y, width, 1, ""),
            )
        )
    why_label_box = fltk.Fl_Box(x, y, width, 1, "Why here")
    why_text_box = fltk.Fl_Box(x, y, width, 1, "")
    group.end()

    widgets = DigestThreadCardWidgets(
        group=group,
        surface=surface,
        title_box=title_box,
        summary_box=summary_box,
        source_posts=source_posts,
        why_label_box=why_label_box,
        why_text_box=why_text_box,
    )
    update_digest_thread_card(
        widgets=widgets,
        x=x,
        y=y,
        width=width,
        thread_index=thread_index,
        thread_card=thread_card,
        theme=theme,
    )
    return widgets


def update_digest_thread_card(
    *,
    widgets: DigestThreadCardWidgets,
    x: int,
    y: int,
    width: int,
    thread_index: int,
    thread_card,
    theme: UiTheme,
) -> None:
    widgets.group.show()
    _layout_digest_thread_card(
        widgets=widgets,
        x=x,
        y=y,
        width=width,
        thread_index=thread_index,
        thread_card=thread_card,
    )
    apply_digest_thread_card_theme(widgets, theme=theme)


def hide_digest_thread_card(widgets: DigestThreadCardWidgets) -> None:
    widgets.group.hide()


def build_digest_empty_state(
    *,
    parent,
    x: int,
    y: int,
    width: int,
    message: str,
    theme: UiTheme,
):
    empty_box = fltk.Fl_Box(x, y, width, 72, message)
    parent.add(empty_box)
    empty_box.box(fltk.FL_BORDER_BOX)
    empty_box.color(to_fltk_color(fltk, theme.viewer_plain_bg))
    empty_box.labelcolor(to_fltk_color(fltk, theme.muted_text))
    empty_box.labelfont(fltk.FL_HELVETICA_ITALIC)
    empty_box.labelsize(14)
    empty_box.align(fltk.FL_ALIGN_LEFT | fltk.FL_ALIGN_INSIDE | fltk.FL_ALIGN_WRAP)
    return empty_box


def apply_digest_thread_card_theme(
    widgets: DigestThreadCardWidgets,
    *,
    theme: UiTheme,
) -> None:
    panel_color = to_fltk_color(fltk, theme.viewer_plain_bg)
    text_color = to_fltk_color(fltk, theme.text)
    muted_color = to_fltk_color(fltk, theme.muted_text)

    widgets.surface.box(fltk.FL_BORDER_BOX)
    widgets.surface.color(panel_color)

    for box in (
        widgets.title_box,
        widgets.summary_box,
        widgets.why_label_box,
        widgets.why_text_box,
    ):
        box.box(fltk.FL_FLAT_BOX)
        box.color(panel_color)
        box.align(fltk.FL_ALIGN_LEFT | fltk.FL_ALIGN_INSIDE | fltk.FL_ALIGN_WRAP)

    widgets.title_box.labelcolor(text_color)
    widgets.title_box.labelfont(TITLE_FONT)
    widgets.title_box.labelsize(TITLE_SIZE)

    widgets.summary_box.labelcolor(text_color)
    widgets.summary_box.labelfont(SUMMARY_FONT)
    widgets.summary_box.labelsize(SUMMARY_SIZE)

    widgets.why_label_box.labelcolor(muted_color)
    widgets.why_label_box.labelfont(WHY_LABEL_FONT)
    widgets.why_label_box.labelsize(WHY_LABEL_SIZE)

    widgets.why_text_box.labelcolor(text_color)
    widgets.why_text_box.labelfont(WHY_TEXT_FONT)
    widgets.why_text_box.labelsize(WHY_TEXT_SIZE)

    for source_post in widgets.source_posts:
        source_post.meta_box.box(fltk.FL_FLAT_BOX)
        source_post.meta_box.color(panel_color)
        source_post.meta_box.align(
            fltk.FL_ALIGN_LEFT | fltk.FL_ALIGN_INSIDE | fltk.FL_ALIGN_WRAP
        )
        source_post.meta_box.labelcolor(muted_color)
        source_post.meta_box.labelfont(SOURCE_META_FONT)
        source_post.meta_box.labelsize(SOURCE_META_SIZE)

        source_post.text_box.box(fltk.FL_FLAT_BOX)
        source_post.text_box.color(panel_color)
        source_post.text_box.align(
            fltk.FL_ALIGN_LEFT | fltk.FL_ALIGN_INSIDE | fltk.FL_ALIGN_WRAP
        )
        source_post.text_box.labelcolor(text_color)
        source_post.text_box.labelfont(SOURCE_TEXT_FONT)
        source_post.text_box.labelsize(SOURCE_TEXT_SIZE)


def thread_cards_total_height(cards: list[DigestThreadCardWidgets]) -> int:
    if not cards:
        return CARD_LIST_PADDING * 2
    return cards[-1].group.y() + cards[-1].group.h() + CARD_LIST_PADDING


def _layout_digest_thread_card(
    *,
    widgets: DigestThreadCardWidgets,
    x: int,
    y: int,
    width: int,
    thread_index: int,
    thread_card,
) -> None:
    inner_x = x + CARD_PADDING_X
    inner_width = max(1, width - (CARD_PADDING_X * 2))
    source_text_width = max(1, inner_width - CARD_SOURCE_TEXT_INDENT)

    title_text = _wrap_text_to_width(
        text=f"{thread_index:02d}. {thread_card.title}",
        font=TITLE_FONT,
        size=TITLE_SIZE,
        max_width=max(1, inner_width - (CARD_BORDER * 2)),
    )
    title_height = _measure_text_height(title_text, font=TITLE_FONT, size=TITLE_SIZE)

    summary_text = _wrap_text_to_width(
        text=thread_card.summary,
        font=SUMMARY_FONT,
        size=SUMMARY_SIZE,
        max_width=max(1, inner_width - (CARD_BORDER * 2)),
    )
    summary_height = _measure_text_height(summary_text, font=SUMMARY_FONT, size=SUMMARY_SIZE)

    source_layouts: list[tuple[str, int, str, int]] = []
    source_total_height = 0
    for tweet_index, tweet in enumerate(thread_card.tweets, start=1):
        meta_text = _wrap_text_to_width(
            text=(
                f"Source post {tweet_index:02d}. @{tweet.author_handle} | "
                f"{tweet.kind} | {_format_timestamp(tweet.created_at)}"
            ),
            font=SOURCE_META_FONT,
            size=SOURCE_META_SIZE,
            max_width=max(1, inner_width - (CARD_BORDER * 2)),
        )
        meta_height = _measure_text_height(
            meta_text,
            font=SOURCE_META_FONT,
            size=SOURCE_META_SIZE,
        )
        tweet_text = _wrap_text_to_width(
            text=tweet.text,
            font=SOURCE_TEXT_FONT,
            size=SOURCE_TEXT_SIZE,
            max_width=max(1, source_text_width - (CARD_BORDER * 2)),
        )
        tweet_height = _measure_text_height(
            tweet_text,
            font=SOURCE_TEXT_FONT,
            size=SOURCE_TEXT_SIZE,
        )
        source_layouts.append((meta_text, meta_height, tweet_text, tweet_height))
        source_total_height += meta_height + 4 + tweet_height + CARD_SOURCE_GAP

    why_label_text = "Why here"
    why_label_height = _measure_text_height(
        why_label_text,
        font=WHY_LABEL_FONT,
        size=WHY_LABEL_SIZE,
    )
    why_text = _wrap_text_to_width(
        text=thread_card.why_it_matters,
        font=WHY_TEXT_FONT,
        size=WHY_TEXT_SIZE,
        max_width=max(1, inner_width - (CARD_BORDER * 2)),
    )
    why_text_height = _measure_text_height(
        why_text,
        font=WHY_TEXT_FONT,
        size=WHY_TEXT_SIZE,
    )

    total_height = (
        CARD_PADDING_Y
        + title_height
        + CARD_SECTION_GAP
        + summary_height
        + CARD_SECTION_GAP
        + source_total_height
        + why_label_height
        + 2
        + why_text_height
        + CARD_BOTTOM_PADDING
        + CARD_PADDING_Y
    )
    widgets.group.resize(x, y, width, total_height)
    widgets.surface.resize(x, y, width, total_height)

    current_y = y + CARD_PADDING_Y
    widgets.title_box.label(title_text)
    widgets.title_box.resize(inner_x, current_y, inner_width, title_height)
    current_y += title_height + CARD_SECTION_GAP

    widgets.summary_box.label(summary_text)
    widgets.summary_box.resize(inner_x, current_y, inner_width, summary_height)
    current_y += summary_height + CARD_SECTION_GAP

    for source_post, (meta_text, meta_height, tweet_text, tweet_height) in zip(
        widgets.source_posts,
        source_layouts,
        strict=False,
    ):
        source_post.meta_box.label(meta_text)
        source_post.meta_box.resize(inner_x, current_y, inner_width, meta_height)
        current_y += meta_height + 4
        source_post.text_box.label(tweet_text)
        source_post.text_box.resize(
            inner_x + CARD_SOURCE_TEXT_INDENT,
            current_y,
            source_text_width,
            tweet_height,
        )
        current_y += tweet_height + CARD_SOURCE_GAP

    widgets.why_label_box.label(why_label_text)
    widgets.why_label_box.resize(inner_x, current_y, inner_width, why_label_height)
    current_y += why_label_height + 8
    widgets.why_text_box.label(why_text)
    widgets.why_text_box.resize(inner_x, current_y, inner_width, why_text_height)


def _measure_text_height(text: str, *, font: int, size: int) -> int:
    fltk.fl_font(font, size)
    line_height = max(1, fltk.fl_height(font, size))
    line_count = max(1, text.count("\n") + 1)
    return (line_count * line_height) + 4


def _wrap_text_to_width(
    *,
    text: str,
    font: int,
    size: int,
    max_width: int,
) -> str:
    fltk.fl_font(font, size)
    wrapped_lines: list[str] = []
    for raw_paragraph in text.splitlines() or [""]:
        paragraph = raw_paragraph.strip()
        if not paragraph:
            wrapped_lines.append("")
            continue
        current_line = ""
        for word in paragraph.split():
            candidate = word if not current_line else f"{current_line} {word}"
            if fltk.fl_width(candidate) <= max_width:
                current_line = candidate
                continue
            if current_line:
                wrapped_lines.append(current_line)
                current_line = ""
            wrapped_lines.extend(
                _wrap_long_word(
                    word=word,
                    max_width=max_width,
                )
            )
        if current_line:
            wrapped_lines.append(current_line)
    return "\n".join(wrapped_lines)


def _wrap_long_word(*, word: str, max_width: int) -> list[str]:
    wrapped: list[str] = []
    current = ""
    for character in word:
        candidate = f"{current}{character}"
        if current and fltk.fl_width(candidate) > max_width:
            wrapped.append(current)
            current = character
        else:
            current = candidate
    if current:
        wrapped.append(current)
    return wrapped or [word]


def _format_timestamp(value) -> str:  # noqa: ANN001
    if value is None:
        return "n/a"
    return value.strftime("%Y-%m-%d %H:%M UTC")

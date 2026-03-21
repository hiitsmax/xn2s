from __future__ import annotations

import fltk

from xs2n.ui.digest_browser import DigestBrowser
from xs2n.ui.digest_browser_state import DigestBrowserState

from test_digest_browser_state import _preview


def test_digest_browser_layout_insets_the_issue_summary_surface() -> None:
    browser = DigestBrowser(
        x=0,
        y=0,
        width=1000,
        height=700,
        on_open_url=lambda _url: None,
    )

    assert browser.issue_summary_surface.x() < browser.issue_title.x()
    assert browser.issue_summary_surface.y() < browser.issue_title.y()
    assert browser.issue_summary_surface.w() > browser.issue_title.w()
    assert browser.issue_summary_surface.h() > (
        browser.issue_title.h()
        + browser.issue_meta.h()
        + browser.issue_blurb.h()
    )
    assert browser.open_button.y() > (
        browser.issue_summary_surface.y() + browser.issue_summary_surface.h()
    )


def test_digest_browser_layout_places_sort_headers_above_issue_list() -> None:
    browser = DigestBrowser(
        x=0,
        y=0,
        width=1000,
        height=700,
        on_open_url=lambda _url: None,
    )

    assert browser.issue_title_header.x() == browser.issue_list.x()
    assert browser.issue_thread_count_header.y() == browser.issue_title_header.y()
    assert browser.issue_thread_count_header.x() > browser.issue_title_header.x()
    assert browser.issue_list.y() > browser.issue_title_header.y()


def test_digest_browser_resize_rebalances_issue_list_and_reader_widths() -> None:
    browser = DigestBrowser(
        x=0,
        y=0,
        width=1320,
        height=920,
        on_open_url=lambda _url: None,
    )

    initial_list_width = browser.issue_list.w()
    initial_reader_width = browser.issue_thread_scroll.w()

    browser.resize(0, 0, 900, 720)
    narrow_list_width = browser.issue_list.w()
    narrow_reader_width = browser.issue_thread_scroll.w()

    browser.resize(0, 0, 1600, 900)
    wide_list_width = browser.issue_list.w()
    wide_reader_width = browser.issue_thread_scroll.w()

    assert narrow_list_width < initial_list_width
    assert wide_list_width > initial_list_width
    assert narrow_reader_width > narrow_list_width
    assert wide_reader_width > wide_list_width


def test_digest_browser_renders_native_thread_cards_for_selected_issue() -> None:
    browser = DigestBrowser(
        x=0,
        y=0,
        width=1000,
        height=700,
        on_open_url=lambda _url: None,
    )
    browser._state = DigestBrowserState(_preview())

    browser._render()

    assert hasattr(browser, "issue_thread_scroll")
    assert len(browser._issue_thread_cards) == 2
    first_card = browser._issue_thread_cards[0]
    assert first_card.surface.box() == fltk.FL_BORDER_BOX
    assert first_card.title_box.labelfont() == fltk.FL_HELVETICA_BOLD
    assert first_card.why_label_box.labelfont() == fltk.FL_HELVETICA_ITALIC
    assert first_card.title_box.x() > first_card.surface.x()
    assert first_card.summary_box.y() > first_card.title_box.y()
    assert first_card.why_text_box.y() > first_card.source_posts[0].text_box.y()
    assert first_card.why_text_box.y() >= (
        first_card.why_label_box.y() + first_card.why_label_box.h() + 4
    )

from __future__ import annotations

from xs2n.ui.digest_browser import DigestBrowser


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

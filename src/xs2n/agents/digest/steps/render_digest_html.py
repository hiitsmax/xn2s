from __future__ import annotations

import html

from xs2n.schemas.digest import Issue, IssueThread


def _source_links_html(urls: list[str]) -> str:
    if not urls:
        return '<span class="muted">No direct source link captured.</span>'
    return " ".join(
        f'<a href="{html.escape(url)}" target="_blank" rel="noreferrer">source {index + 1}</a>'
        for index, url in enumerate(urls)
    )


def run(
    *,
    run_id: str,
    digest_title: str,
    issues: list[Issue],
    issue_threads: list[IssueThread],
) -> str:
    by_thread_id = {thread.thread_id: thread for thread in issue_threads}
    issue_sections: list[str] = []

    for issue in issues:
        members = [
            by_thread_id[thread_id]
            for thread_id in issue.thread_ids
            if thread_id in by_thread_id
        ]
        thread_cards = "".join(
            (
                '<article class="thread-card">'
                f"<h4>{html.escape(thread.thread_title)}</h4>"
                f"<p>{html.escape(thread.thread_summary)}</p>"
                f'<p class="muted">{html.escape(thread.why_this_thread_belongs)}</p>'
                f'<p class="links">{_source_links_html(thread.source_urls)}</p>'
                "</article>"
            )
            for thread in members
        )
        issue_sections.append(
            (
                '<section class="issue">'
                f"<h2>{html.escape(issue.title)}</h2>"
                f"<p>{html.escape(issue.summary)}</p>"
                f"{thread_cards}"
                "</section>"
            )
        )

    empty_state = ""
    if not issue_sections:
        empty_state = (
            '<section class="issue empty">'
            "<h2>No issue digest produced</h2>"
            "<p>No threads survived the loose filter in this run.</p>"
            "</section>"
        )

    return (
        "<!doctype html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8" />'
        f"<title>{html.escape(digest_title)}</title>"
        '<meta name="viewport" content="width=device-width, initial-scale=1" />'
        "<style>"
        "body{margin:0;padding:16px;background:#C0C0C0;color:#000;"
        "font-family:'MS Sans Serif',Tahoma,Verdana,sans-serif;font-size:14px;}"
        ".page{max-width:920px;margin:0 auto;border:2px solid #808080;"
        "border-right-color:#404040;border-bottom-color:#404040;background:#D4D0C8;}"
        ".titlebar{background:#000080;color:#FFF;padding:8px 10px;font-weight:bold;}"
        ".body{padding:12px;}"
        ".meta{margin:0 0 12px;color:#333;}"
        ".issue{margin-bottom:12px;border:2px solid #808080;border-right-color:#FFF;"
        "border-bottom-color:#FFF;background:#EFEFE7;padding:10px;}"
        ".issue h2,.thread-card h4{margin:0 0 8px;font-size:16px;}"
        ".thread-card{margin-top:10px;padding-top:10px;border-top:1px solid #808080;}"
        ".muted{color:#444;}"
        ".links a{color:#000080;text-decoration:underline;margin-right:10px;}"
        ".empty{background:#E8E8E0;}"
        "</style>"
        "</head>"
        "<body>"
        '<div class="page">'
        f'<div class="titlebar">{html.escape(digest_title)}</div>'
        '<div class="body">'
        f"<p class=\"meta\">Run {html.escape(run_id)}</p>"
        f"{''.join(issue_sections) or empty_state}"
        "</div>"
        "</div>"
        "</body>"
        "</html>"
    )

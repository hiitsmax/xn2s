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
        ":root{"
        "--bg:#f7f3ea;--fg:#1f1a15;--muted:#6f6253;--panel:#fffdf9;"
        "--panel-border:#e3dbcf;--header-border:#d6ccbd;--link:#6b3f24;"
        "--empty:#f2eee6;"
        "}"
        "@media (prefers-color-scheme: dark){"
        ":root{"
        "--bg:#1f1d19;--fg:#ddd7c8;--muted:#a8a08f;--panel:#26241f;"
        "--panel-border:#4a463f;--header-border:#4a463f;--link:#f5f1e6;"
        "--empty:#3b3833;"
        "}"
        "}"
        "body{margin:0;background:var(--bg);color:var(--fg);font-family:Georgia,serif;}"
        ".page{max-width:860px;margin:0 auto;padding:48px 24px 72px;}"
        "header{margin-bottom:36px;border-bottom:1px solid var(--header-border);padding-bottom:20px;}"
        "h1,h2,h4{font-weight:600;line-height:1.15;margin:0 0 12px;}"
        "h1{font-size:40px;}h2{font-size:28px;}h4{font-size:20px;}"
        "p{font-size:18px;line-height:1.55;margin:0 0 12px;color:var(--fg);}"
        ".meta,.muted{color:var(--muted);font-size:15px;}"
        ".issue{background:var(--panel);border:1px solid var(--panel-border);padding:24px;margin-bottom:24px;}"
        ".thread-card{border-top:1px solid var(--header-border);margin-top:18px;padding-top:18px;}"
        ".links a{color:var(--link);text-decoration:none;margin-right:10px;}"
        ".empty{background:var(--empty);}"
        "</style>"
        "</head>"
        "<body>"
        '<main class="page">'
        "<header>"
        f"<p class=\"meta\">Run {html.escape(run_id)}</p>"
        f"<h1>{html.escape(digest_title)}</h1>"
        "</header>"
        f"{''.join(issue_sections) or empty_state}"
        "</main>"
        "</body>"
        "</html>"
    )

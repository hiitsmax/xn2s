from __future__ import annotations

from dataclasses import dataclass
import html
import json
from pathlib import Path
from typing import Any

from xs2n.schemas.digest import Issue, IssueThread
from xs2n.ui.fonts import DEFAULT_UI_HTML_FONT_FAMILY
from xs2n.ui.theme import CLASSIC_LIGHT_THEME, UiTheme


@dataclass(slots=True)
class SavedDigestPreview:
    run_id: str
    digest_title: str
    issues: list[Issue]
    issue_threads: list[IssueThread]


def render_saved_digest_preview_html(
    *,
    artifact_path: Path,
    theme: UiTheme = CLASSIC_LIGHT_THEME,
) -> str | None:
    preview = load_saved_digest_preview(run_dir=artifact_path.parent)
    if preview is None:
        return None

    metadata_rows = "".join(
        (
            "<tr>"
            f"<td width=\"96\"><b>{_wrap_default_ui_face(html.escape(label))}:</b></td>"
            f"<td>{_wrap_default_ui_face(html.escape(value))}</td>"
            "</tr>"
        )
        for label, value in {
            "path": str(artifact_path),
            "kind": "html",
            "run": preview.run_id,
            "issues": str(len(preview.issues)),
            "threads": str(len(preview.issue_threads)),
        }.items()
    )
    metadata_html = (
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"6\" "
        f'bgcolor="{theme.header_bg}">'
        f"{metadata_rows}"
        "</table>"
        "<p></p>"
    )

    issue_threads_by_id = {
        thread.thread_id: thread for thread in preview.issue_threads
    }
    body_parts: list[str] = []
    if not preview.issues:
        body_parts.append(
            (
                f"<h2>{_wrap_default_ui_face('No issue digest produced')}</h2>"
                "<p>"
                f"{_wrap_default_ui_face('No threads survived the loose filter in this run.')}"
                "</p>"
            )
        )

    for issue in preview.issues:
        body_parts.append(
            f"<h2>{_wrap_default_ui_face(html.escape(issue.title))}</h2>"
        )
        body_parts.append(
            f"<p>{_wrap_default_ui_face(html.escape(issue.summary))}</p>"
        )

        for thread_id in issue.thread_ids:
            thread = issue_threads_by_id.get(thread_id)
            if thread is None:
                continue
            body_parts.append(
                (
                    "<p>"
                    f"<b>{_wrap_default_ui_face(html.escape(thread.thread_title))}</b><br>"
                    f"{_wrap_default_ui_face(html.escape(thread.thread_summary))}<br>"
                    f"<font color=\"{theme.muted_text}\">"
                    f"{_wrap_default_ui_face(html.escape(thread.why_this_thread_belongs))}"
                    "</font><br>"
                    f"{_source_links_html(thread.source_urls, theme=theme)}"
                    "</p>"
                )
            )

        body_parts.append("<p></p>")

    return (
        "<html>"
        f'<body bgcolor="{theme.viewer_bg}" text="{theme.text}">'
        f"<font face=\"{DEFAULT_UI_HTML_FONT_FAMILY}\" size=\"3\">"
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"8\" "
        f'bgcolor="{theme.viewer_panel_bg}">'
        "<tr>"
        f"<td><b>{_wrap_default_ui_face(html.escape(preview.digest_title))}</b></td>"
        "</tr>"
        "</table>"
        "<p></p>"
        f"{metadata_html}"
        f"{''.join(body_parts)}"
        "</font>"
        "</body>"
        "</html>"
    )


def load_saved_digest_preview(*, run_dir: Path) -> SavedDigestPreview | None:
    issues_doc = _load_json(run_dir / "issues.json")
    issue_threads_doc = _load_json(run_dir / "issue_assignments.json")
    if not isinstance(issues_doc, list) or not isinstance(issue_threads_doc, list):
        return None

    issues = _load_models(issues_doc, Issue)
    issue_threads = _load_models(issue_threads_doc, IssueThread)
    if issues is None or issue_threads is None:
        return None

    run_doc = _load_json_dict(run_dir / "run.json") or {}
    run_id = str(run_doc.get("run_id") or run_dir.name)
    digest_title = str(
        run_doc.get("digest_title")
        or (issues[0].title if issues else "No issue digest produced")
    )
    return SavedDigestPreview(
        run_id=run_id,
        digest_title=digest_title,
        issues=issues,
        issue_threads=issue_threads,
    )


def _source_links_html(urls: list[str], *, theme: UiTheme) -> str:
    if not urls:
        return (
            f'<font color="{theme.muted_text}">'
            f"{_wrap_default_ui_face('No direct source link captured.')}"
            "</font>"
        )
    return " ".join(
        (
            f'<a href="{html.escape(url)}">'
            f'<font color="{theme.selection_bg}">'
            f"{_wrap_default_ui_face(f'source {index + 1}')}"
            "</font>"
            "</a>"
        )
        for index, url in enumerate(urls)
    )


def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _load_json_dict(path: Path) -> dict[str, Any] | None:
    payload = _load_json(path)
    if isinstance(payload, dict):
        return payload
    return None


def _load_models(payload: list[Any], model_type) -> list[Any] | None:  # noqa: ANN001
    models: list[Any] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            models.append(model_type.model_validate(item))
        except Exception:
            return None
    return models


def _default_ui_face_tag() -> str:
    return f'<font face="{DEFAULT_UI_HTML_FONT_FAMILY}">'


def _wrap_default_ui_face(text: str) -> str:
    return f"{_default_ui_face_tag()}{text}</font>"

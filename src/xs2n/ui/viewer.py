from __future__ import annotations

import html
import re
from typing import Mapping

from xs2n.ui.artifacts import ArtifactRecord, load_artifact_text
from xs2n.ui.openstep import OPENSTEP_FONT_FAMILY

try:
    import markdown as markdown_lib
except ImportError:  # pragma: no cover - optional GUI dependency
    markdown_lib = None


MARKDOWN_EXTENSIONS = [
    "fenced_code",
    "tables",
]
MARKDOWN_BODY_WIDTH = "98%"
MARKDOWN_BODY_PADDING = 12
OPENSTEP_FONT_BLOCK_TAGS = (
    "blockquote",
    "dd",
    "dt",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "p",
    "pre",
    "td",
    "th",
)


def render_artifact_html(artifact: ArtifactRecord) -> str:
    body = load_artifact_text(artifact.path)
    metadata = {
        "path": str(artifact.path),
        "kind": artifact.kind,
    }
    if artifact.phase_name is not None:
        metadata["phase"] = artifact.phase_name

    if artifact.kind == "markdown":
        body_html = _render_markdown_html(body)
    else:
        body_html = _render_plain_text_block(body)

    return _wrap_html_document(
        title=artifact.name,
        metadata=metadata,
        body_html=body_html,
    )


def render_plain_text_html(
    *,
    title: str,
    body: str,
    metadata: Mapping[str, str] | None = None,
) -> str:
    return _wrap_html_document(
        title=title,
        metadata=metadata,
        body_html=_render_plain_text_block(body),
    )


def _wrap_html_document(
    *,
    title: str,
    metadata: Mapping[str, str] | None,
    body_html: str,
) -> str:
    metadata_rows = ""
    if metadata:
        metadata_rows = "".join(
            (
                "<tr>"
                f"<td width=\"96\"><b>{_wrap_openstep_face(html.escape(label))}:</b></td>"
                f"<td>{_wrap_openstep_face(html.escape(value))}</td>"
                "</tr>"
            )
            for label, value in metadata.items()
        )

    metadata_html = ""
    if metadata_rows:
        metadata_html = (
            "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"6\" "
            "bgcolor=\"#d8d2c2\">"
            f"{metadata_rows}"
            "</table>"
            "<p></p>"
        )

    return (
        "<html>"
        "<body bgcolor=\"#ece8dc\" text=\"#111111\">"
        f"<font face=\"{OPENSTEP_FONT_FAMILY}\" size=\"3\">"
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"8\" "
        "bgcolor=\"#cfc8b6\">"
        "<tr>"
        f"<td><b>{_wrap_openstep_face(html.escape(title))}</b></td>"
        "</tr>"
        "</table>"
        "<p></p>"
        f"{metadata_html}"
        f"{body_html}"
        "</font>"
        "</body>"
        "</html>"
    )


def _render_markdown_html(markdown_text: str) -> str:
    if markdown_lib is None:
        return _render_plain_text_block(markdown_text)

    rendered = markdown_lib.markdown(
        markdown_text,
        extensions=MARKDOWN_EXTENSIONS,
        output_format="html",
    )
    if not rendered:
        return _render_plain_text_block(markdown_text)

    rendered = _apply_openstep_font_family(rendered)

    return (
        f"<table width=\"{MARKDOWN_BODY_WIDTH}\" align=\"center\" "
        f"cellspacing=\"0\" cellpadding=\"{MARKDOWN_BODY_PADDING}\">"
        "<tr>"
        f"<td>{rendered}</td>"
        "</tr>"
        "</table>"
    )


def _render_plain_text_block(text: str) -> str:
    return (
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"8\" "
        "bgcolor=\"#f6f4ed\">"
        "<tr>"
        "<td>"
        f"<pre><font face=\"{OPENSTEP_FONT_FAMILY}\" size=\"3\">"
        f"{html.escape(text)}"
        "</font></pre>"
        "</td>"
        "</tr>"
        "</table>"
    )


def _apply_openstep_font_family(rendered_html: str) -> str:
    tag_pattern = "|".join(OPENSTEP_FONT_BLOCK_TAGS)
    opening_pattern = re.compile(
        rf"<({tag_pattern})(\s[^>]*)?>",
        flags=re.IGNORECASE,
    )
    closing_pattern = re.compile(
        rf"</({tag_pattern})>",
        flags=re.IGNORECASE,
    )
    rendered_html = opening_pattern.sub(
        lambda match: f"{match.group(0)}{_openstep_face_tag()}",
        rendered_html,
    )
    return closing_pattern.sub("</font></\\1>", rendered_html)


def _openstep_face_tag() -> str:
    return f'<font face="{OPENSTEP_FONT_FAMILY}">'


def _wrap_openstep_face(text: str) -> str:
    return f"{_openstep_face_tag()}{text}</font>"

from __future__ import annotations

import html
import re
from typing import Mapping

from xs2n.ui.artifacts import ArtifactPreview, ArtifactRecord, load_artifact_preview
from xs2n.ui.fonts import DEFAULT_UI_FONT_FAMILY, DEFAULT_UI_HTML_FONT_FAMILY
from xs2n.ui.theme import CLASSIC_LIGHT_THEME, UiTheme

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
DEFAULT_UI_FONT_BLOCK_TAGS = (
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
DEFAULT_UI_FONT_TAG_PATTERN = "|".join(DEFAULT_UI_FONT_BLOCK_TAGS)
DEFAULT_UI_FONT_OPENING_PATTERN = re.compile(
    rf"<({DEFAULT_UI_FONT_TAG_PATTERN})(\s[^>]*)?>",
    flags=re.IGNORECASE,
)
DEFAULT_UI_FONT_CLOSING_PATTERN = re.compile(
    rf"</({DEFAULT_UI_FONT_TAG_PATTERN})>",
    flags=re.IGNORECASE,
)


def render_artifact_html(
    artifact: ArtifactRecord,
    *,
    theme: UiTheme = CLASSIC_LIGHT_THEME,
) -> str:
    preview = load_artifact_preview(artifact)
    metadata = _artifact_metadata(artifact, preview)

    if preview.render_kind == "markdown":
        body_html = _render_markdown_html(preview.body, theme=theme)
    elif preview.render_kind == "html":
        return _render_html_artifact(preview.body, theme=theme)
    else:
        body_html = _render_plain_text_block(preview.body, theme=theme)

    return _wrap_html_document(
        title=artifact.name,
        metadata=metadata,
        body_html=body_html,
        theme=theme,
    )


def render_loading_artifact_html(
    artifact: ArtifactRecord,
    *,
    theme: UiTheme = CLASSIC_LIGHT_THEME,
) -> str:
    return render_plain_text_html(
        title=f"Loading {artifact.name}",
        body="Rendering artifact preview...\n",
        metadata=_artifact_metadata(
            artifact,
            ArtifactPreview(body="", render_kind="text"),
        ),
        theme=theme,
    )


def render_plain_text_html(
    *,
    title: str,
    body: str,
    metadata: Mapping[str, str] | None = None,
    theme: UiTheme = CLASSIC_LIGHT_THEME,
) -> str:
    return _wrap_html_document(
        title=title,
        metadata=metadata,
        body_html=_render_plain_text_block(body, theme=theme),
        theme=theme,
    )


def _wrap_html_document(
    *,
    title: str,
    metadata: Mapping[str, str] | None,
    body_html: str,
    theme: UiTheme,
) -> str:
    metadata_rows = ""
    if metadata:
        metadata_rows = "".join(
            (
                "<tr>"
                f"<td width=\"96\"><b>{_wrap_default_ui_face(html.escape(label))}:</b></td>"
                f"<td>{_wrap_default_ui_face(html.escape(value))}</td>"
                "</tr>"
            )
            for label, value in metadata.items()
        )

    metadata_html = ""
    if metadata_rows:
        metadata_html = (
            "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"6\" "
            f'bgcolor="{theme.header_bg}">'
            f"{metadata_rows}"
            "</table>"
            "<p></p>"
        )

    return (
        "<html>"
        f'<body bgcolor="{theme.viewer_bg}" text="{theme.text}">'
        f"<font face=\"{DEFAULT_UI_HTML_FONT_FAMILY}\" size=\"3\">"
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"8\" "
        f'bgcolor="{theme.viewer_panel_bg}">'
        "<tr>"
        f"<td><b>{_wrap_default_ui_face(html.escape(title))}</b></td>"
        "</tr>"
        "</table>"
        "<p></p>"
        f"{metadata_html}"
        f"{body_html}"
        "</font>"
        "</body>"
        "</html>"
    )


def _render_markdown_html(
    markdown_text: str,
    *,
    theme: UiTheme,
) -> str:
    if markdown_lib is None:
        return _render_plain_text_block(markdown_text, theme=theme)

    rendered = markdown_lib.markdown(
        markdown_text,
        extensions=MARKDOWN_EXTENSIONS,
        output_format="html",
    )
    if not rendered:
        return _render_plain_text_block(markdown_text, theme=theme)

    rendered = _apply_default_ui_font_family(rendered)

    return (
        f"<table width=\"{MARKDOWN_BODY_WIDTH}\" align=\"center\" "
        f"cellspacing=\"0\" cellpadding=\"{MARKDOWN_BODY_PADDING}\">"
        "<tr>"
        f"<td>{rendered}</td>"
        "</tr>"
        "</table>"
    )


def _render_html_artifact(
    html_text: str,
    *,
    theme: UiTheme,
) -> str:
    if theme == CLASSIC_LIGHT_THEME:
        return html_text

    override_style = (
        "<style>"
        f"body{{background:{theme.viewer_bg} !important;color:{theme.text} !important;}}"
        f".page{{color:{theme.text} !important;}}"
        f"header{{border-bottom:1px solid {theme.header_bg} !important;}}"
        f"h1,h2,h4,p{{color:{theme.text} !important;}}"
        f".meta,.muted{{color:{theme.muted_text} !important;}}"
        f".issue{{background:{theme.viewer_plain_bg} !important;border:1px solid {theme.header_bg} !important;}}"
        f".thread-card{{border-top:1px solid {theme.header_bg} !important;}}"
        f".links a{{color:{theme.selection_text} !important;}}"
        f".empty{{background:{theme.panel_bg2} !important;}}"
        "</style>"
    )
    if "</head>" in html_text.lower():
        return re.sub(
            r"</head>",
            f"{override_style}</head>",
            html_text,
            count=1,
            flags=re.IGNORECASE,
        )
    return f"{override_style}{html_text}"


def _render_plain_text_block(
    text: str,
    *,
    theme: UiTheme,
) -> str:
    return (
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"8\" "
        f'bgcolor="{theme.viewer_plain_bg}">'
        "<tr>"
        "<td>"
        f"<pre><font face=\"{DEFAULT_UI_FONT_FAMILY}\" size=\"3\">"
        f"{html.escape(text)}"
        "</font></pre>"
        "</td>"
        "</tr>"
        "</table>"
    )


def _artifact_metadata(
    artifact: ArtifactRecord,
    preview: ArtifactPreview,
) -> dict[str, str]:
    metadata = {
        "path": str(artifact.path),
        "kind": artifact.kind,
    }
    if preview.summary is not None:
        metadata["preview"] = preview.summary
    if artifact.phase_name is not None:
        metadata["phase"] = artifact.phase_name
    return metadata


def _apply_default_ui_font_family(rendered_html: str) -> str:
    rendered_html = DEFAULT_UI_FONT_OPENING_PATTERN.sub(
        lambda match: f"{match.group(0)}{_default_ui_face_tag()}",
        rendered_html,
    )
    return DEFAULT_UI_FONT_CLOSING_PATTERN.sub("</font></\\1>", rendered_html)


def _default_ui_face_tag() -> str:
    return f'<font face="{DEFAULT_UI_HTML_FONT_FAMILY}">'


def _wrap_default_ui_face(text: str) -> str:
    return f"{_default_ui_face_tag()}{text}</font>"

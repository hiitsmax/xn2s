from __future__ import annotations

from pathlib import Path

import pytest

from xs2n.ui.artifacts import ArtifactRecord
from xs2n.ui.fonts import DEFAULT_UI_FONT_FAMILY
from xs2n.ui.viewer import render_artifact_html, render_plain_text_html


def test_render_plain_text_html_escapes_markup() -> None:
    html = render_plain_text_html(
        title="command output",
        body="line 1\n<h1>unsafe</h1>\n",
        metadata={"cwd": "/tmp/demo"},
    )

    assert (
        f'<b><font face="{DEFAULT_UI_FONT_FAMILY}">command output</font></b>'
        in html
    )
    assert "&lt;h1&gt;unsafe&lt;/h1&gt;" in html
    assert "<pre>" in html
    assert f'face="{DEFAULT_UI_FONT_FAMILY}"' in html
    assert f'<font face="{DEFAULT_UI_FONT_FAMILY}">/tmp/demo</font>' in html


def test_render_artifact_html_formats_markdown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeMarkdown:
        @staticmethod
        def markdown(
            text: str,
            *,
            extensions: list[str],
            output_format: str,
        ) -> str:
            assert text == "# Digest\n\nBody paragraph.\n"
            assert extensions == ["fenced_code", "tables"]
            assert output_format == "html"
            return "<h1>Digest</h1><p>Body paragraph.</p>"

    monkeypatch.setattr("xs2n.ui.viewer.markdown_lib", FakeMarkdown)

    markdown_path = tmp_path / "digest.md"
    markdown_path.write_text("# Digest\n\nBody paragraph.\n", encoding="utf-8")

    artifact = ArtifactRecord(
        name="digest.md",
        path=markdown_path,
        kind="markdown",
        exists=True,
        phase_name="render_digest",
    )

    html = render_artifact_html(artifact)

    assert f'<h1><font face="{DEFAULT_UI_FONT_FAMILY}">Digest</font></h1>' in html
    assert (
        f'<p><font face="{DEFAULT_UI_FONT_FAMILY}">Body paragraph.</font></p>'
        in html
    )
    assert 'width="98%"' in html
    assert 'cellpadding="12"' in html
    assert f'face="{DEFAULT_UI_FONT_FAMILY}"' in html
    assert "render_digest" in html
    assert str(markdown_path) in html


def test_render_artifact_html_uses_preformatted_block_for_json(
    tmp_path: Path,
) -> None:
    json_path = tmp_path / "run.json"
    json_path.write_text('{"ok": true}\n', encoding="utf-8")

    artifact = ArtifactRecord(
        name="run.json",
        path=json_path,
        kind="json",
        exists=True,
    )

    html = render_artifact_html(artifact)

    assert "<pre>" in html
    assert "&quot;ok&quot;: true" in html
    assert "<h1>" not in html

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xs2n.ui.artifacts import ArtifactRecord
from xs2n.ui.fonts import DEFAULT_UI_FONT_FAMILY, DEFAULT_UI_HTML_FONT_FAMILY
from xs2n.ui.theme import CLASSIC_DARK_THEME
from xs2n.ui.viewer import (
    render_artifact_html,
    render_loading_artifact_html,
    render_plain_text_html,
)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )


def _issue_thread_payload() -> dict[str, object]:
    tweet = {
        "tweet_id": "2032245601216389324",
        "account_handle": "realmcore_",
        "author_handle": "realmcore_",
        "kind": "retweet",
        "created_at": "2026-03-13T00:01:23Z",
        "text": "Foundry capacity is still the gating factor.",
        "conversation_id": "2032245601216389324",
        "favorite_count": 0,
        "retweet_count": 2,
        "reply_count": 0,
        "quote_count": 0,
        "view_count": None,
        "media": [],
    }
    return {
        "thread_id": "2032245601216389324",
        "conversation_id": "2032245601216389324",
        "account_handle": "realmcore_",
        "tweets": [tweet],
        "source_tweet_ids": ["2032245601216389324"],
        "context_tweet_ids": [],
        "latest_created_at": "2026-03-13T00:01:23Z",
        "primary_tweet_id": "2032245601216389324",
        "primary_tweet": tweet,
        "keep": True,
        "filter_reason": "High-signal infrastructure thread.",
        "issue_slug": "chip_race",
        "issue_title": "Chip Race",
        "issue_summary": "Supply constraints keep shaping AI infra.",
        "thread_title": "Foundry capacity is still the gating factor",
        "thread_summary": "A short report on why foundry capacity still drives the roadmap.",
        "why_this_thread_belongs": "It adds concrete evidence to the chip-capacity issue.",
    }


def test_render_plain_text_html_escapes_markup() -> None:
    html = render_plain_text_html(
        title="command output",
        body="line 1\n<h1>unsafe</h1>\n",
        metadata={"cwd": "/tmp/demo"},
    )

    assert (
        f'<b><font face="{DEFAULT_UI_HTML_FONT_FAMILY}">command output</font></b>'
        in html
    )
    assert "&lt;h1&gt;unsafe&lt;/h1&gt;" in html
    assert "<pre>" in html
    assert f'face="{DEFAULT_UI_FONT_FAMILY}"' in html
    assert f'face="{DEFAULT_UI_HTML_FONT_FAMILY}"' in html
    assert f'<font face="{DEFAULT_UI_HTML_FONT_FAMILY}">/tmp/demo</font>' in html


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

    assert (
        f'<h1><font face="{DEFAULT_UI_HTML_FONT_FAMILY}">Digest</font></h1>'
        in html
    )
    assert (
        f'<p><font face="{DEFAULT_UI_HTML_FONT_FAMILY}">Body paragraph.</font></p>'
        in html
    )
    assert 'width="98%"' in html
    assert 'cellpadding="12"' in html
    assert f'face="{DEFAULT_UI_HTML_FONT_FAMILY}"' in html
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


def test_render_loading_artifact_html_reuses_artifact_metadata(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "categorized_threads.json"
    artifact_path.write_text("[]\n", encoding="utf-8")

    artifact = ArtifactRecord(
        name="categorized_threads.json",
        path=artifact_path,
        kind="json",
        exists=True,
        phase_name="categorize_threads",
    )

    html = render_loading_artifact_html(artifact)

    assert "Loading categorized_threads.json" in html
    assert "Rendering artifact preview..." in html
    assert str(artifact_path) in html
    assert "categorize_threads" in html


def test_render_artifact_html_uses_dark_theme_when_provided(
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
    )

    html = render_artifact_html(artifact, theme=CLASSIC_DARK_THEME)

    assert "#1F1D19" in html
    assert "#4A463F" in html
    assert "#DDD7C8" in html


def test_render_artifact_html_reports_truncated_preview_metadata(
    tmp_path: Path,
) -> None:
    json_path = tmp_path / "large.json"
    json_path.write_text(
        "{\"payload\":\"" + ("x" * 90000) + "\"}\n",
        encoding="utf-8",
    )

    artifact = ArtifactRecord(
        name="large.json",
        path=json_path,
        kind="json",
        exists=True,
    )

    html = render_artifact_html(artifact)

    assert "preview" in html.lower()
    assert "truncated" in html.lower()
    assert "<pre>" in html
    assert "<h1>" not in html


def test_render_artifact_html_returns_html_artifact_verbatim(
    tmp_path: Path,
) -> None:
    html_path = tmp_path / "digest.html"
    html_path.write_text(
        "<!doctype html><html><body><h1>Chip Race</h1></body></html>\n",
        encoding="utf-8",
    )

    artifact = ArtifactRecord(
        name="digest.html",
        path=html_path,
        kind="html",
        exists=True,
    )

    rendered = render_artifact_html(artifact)

    assert "<h1>Chip Race</h1>" in rendered
    assert "<!doctype html>" in rendered.lower()


def test_render_artifact_html_themes_html_artifact_when_dark(
    tmp_path: Path,
) -> None:
    html_path = tmp_path / "digest.html"
    html_path.write_text(
        (
            "<!doctype html><html><head><style>"
            "body{background:#f7f3ea;color:#1f1a15;}"
            ".issue{background:#fffdf9;border:1px solid #e3dbcf;}"
            "</style></head><body><main class=\"page\"><h1>Chip Race</h1>"
            "<section class=\"issue\"><p>Body paragraph.</p></section>"
            "</main></body></html>\n"
        ),
        encoding="utf-8",
    )

    artifact = ArtifactRecord(
        name="digest.html",
        path=html_path,
        kind="html",
        exists=True,
    )

    rendered = render_artifact_html(artifact, theme=CLASSIC_DARK_THEME)

    assert "<h1>Chip Race</h1>" in rendered
    assert "#1F1D19" in rendered
    assert "#DDD7C8" in rendered
    assert "#26241F" in rendered


def test_render_artifact_html_rebuilds_saved_digest_html_for_help_view(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "20260318T225654Z"
    run_dir.mkdir()

    html_path = run_dir / "digest.html"
    html_path.write_text(
        (
            "<!doctype html><html><head><style>"
            "body{background:#f7f3ea;color:#1f1a15;}"
            "</style></head><body><main class=\"page\">"
            "<h1>Browser Shell</h1>"
            "</main></body></html>\n"
        ),
        encoding="utf-8",
    )
    _write_json(
        run_dir / "run.json",
        {
            "run_id": "20260318T225654Z",
            "digest_title": "Chip Race",
        },
    )
    _write_json(
        run_dir / "issues.json",
        [
            {
                "slug": "chip_race",
                "title": "Chip Race",
                "summary": "Supply constraints keep shaping AI infra.",
                "thread_ids": ["2032245601216389324"],
                "thread_count": 1,
            }
        ],
    )
    _write_json(
        run_dir / "issue_assignments.json",
        [_issue_thread_payload()],
    )

    artifact = ArtifactRecord(
        name="digest.html",
        path=html_path,
        kind="html",
        exists=True,
    )

    rendered = render_artifact_html(artifact)

    assert "Chip Race" in rendered
    assert "Supply constraints keep shaping AI infra." in rendered
    assert "Foundry capacity is still the gating factor" in rendered
    assert "source 1" in rendered
    assert "Browser Shell" not in rendered
    assert "<style>" not in rendered
    assert "<main class=" not in rendered

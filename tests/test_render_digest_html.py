from __future__ import annotations

from xs2n.agents.digest.steps.render_digest_html import run


def test_render_digest_html_includes_dark_palette_overrides() -> None:
    rendered = run(
        run_id="20260318T224700Z",
        digest_title="Chip Race",
        issues=[],
        issue_threads=[],
    )

    assert "prefers-color-scheme: dark" in rendered
    assert "--bg:#1f1d19" in rendered
    assert "--fg:#ddd7c8" in rendered
    assert "No issue digest produced" in rendered

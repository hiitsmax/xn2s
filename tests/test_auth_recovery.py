from __future__ import annotations

import subprocess

import pytest
from twikit.errors import Forbidden

from xs2n.profile.auth import is_cloudflare_block_error
from xs2n.profile.playwright import (
    install_playwright_chromium,
    is_missing_playwright_browser_error,
)


def test_is_cloudflare_block_error_true_for_cloudflare_403() -> None:
    error = Forbidden('status: 403, message: "Attention Required! | Cloudflare"')
    assert is_cloudflare_block_error(error) is True


def test_is_cloudflare_block_error_false_for_non_cloudflare_403() -> None:
    error = Forbidden('status: 403, message: "Forbidden"')
    assert is_cloudflare_block_error(error) is False


def test_is_missing_playwright_browser_error_true_for_missing_executable() -> None:
    error = RuntimeError(
        "BrowserType.launch: Executable doesn't exist at /tmp/chromium "
        "Please run the following command to download new browsers: playwright install"
    )
    assert is_missing_playwright_browser_error(error) is True


def test_is_missing_playwright_browser_error_false_for_generic_error() -> None:
    error = RuntimeError("network timeout")
    assert is_missing_playwright_browser_error(error) is False


def test_install_playwright_chromium_raises_with_details_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        return subprocess.CompletedProcess(
            args=["python", "-m", "playwright", "install", "chromium"],
            returncode=1,
            stdout="",
            stderr="permission denied",
        )

    monkeypatch.setattr("xs2n.profile.playwright.subprocess.run", fake_run)

    with pytest.raises(RuntimeError) as error:
        install_playwright_chromium()

    assert "Automatic Chromium install failed" in str(error.value)
    assert "permission denied" in str(error.value)

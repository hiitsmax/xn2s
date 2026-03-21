from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import typer

from xs2n.schemas.auth import (
    extract_valid_x_session_cookies,
    require_valid_x_session_cookies,
)


def is_missing_playwright_browser_error(error: Exception) -> bool:
    text = str(error).lower()
    markers = (
        "executable doesn't exist",
        "playwright install",
        "please run the following command to download new browsers",
    )
    return any(marker in text for marker in markers)


def install_playwright_chromium() -> None:
    command = [sys.executable, "-m", "playwright", "install", "chromium"]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return

    details = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
    raise RuntimeError(
        "Automatic Chromium install failed. Run "
        "`uv run playwright install chromium` and retry. "
        f"Details: {details}"
    )


def _extract_cookies(raw_cookies: list[dict[str, Any]]) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for cookie in raw_cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if isinstance(name, str) and isinstance(value, str):
            cookies[name] = value
    return cookies


def _wait_for_x_session_cookies(
    *,
    context: Any,
    page: Any,
    timeout_seconds: int = 300,
    poll_interval_ms: int = 1000,
) -> dict[str, str] | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        cookies = extract_valid_x_session_cookies(
            _extract_cookies(context.cookies("https://x.com"))
        )
        if cookies is not None:
            return cookies
        page.wait_for_timeout(poll_interval_ms)
    return extract_valid_x_session_cookies(
        _extract_cookies(context.cookies("https://x.com"))
    )


def bootstrap_cookies_via_browser(cookies_file: Path) -> Path:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright dependency is missing in this environment. "
            "Run `uv sync` and retry."
        ) from exc

    cookies_path = cookies_file.expanduser().resolve()
    cookies_path.parent.mkdir(parents=True, exist_ok=True)

    typer.echo("Opening browser for X login...")
    typer.echo(
        "Complete the X login in the browser window. "
        "Cookies will be saved automatically once the session is ready."
    )

    cookies: dict[str, str] | None = None
    for attempt in range(2):
        browser: Any = None
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
                page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded")
                cookies = _wait_for_x_session_cookies(
                    context=context,
                    page=page,
                )
                break
        except Exception as exc:
            if attempt == 0 and is_missing_playwright_browser_error(exc):
                typer.echo("Chromium is missing for Playwright. Installing it now...")
                install_playwright_chromium()
                typer.echo("Chromium installed. Re-opening browser login...")
                continue
            raise RuntimeError(
                "Browser login failed. Ensure Chromium is installed with "
                "`uv run playwright install chromium` and retry."
            ) from exc
        finally:
            if browser is not None:
                browser.close()

    cookies = require_valid_x_session_cookies(
        cookies,
        error_message=(
            "Login appears incomplete: required X session cookies were not found. "
            "Confirm the browser completed login and retry."
        ),
    )

    cookies_path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
    return cookies_path

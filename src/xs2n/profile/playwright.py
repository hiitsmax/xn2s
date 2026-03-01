from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import typer


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
    typer.echo("After login completes in the browser, come back here and confirm.")

    cookies: dict[str, str] = {}
    for attempt in range(2):
        browser: Any = None
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
                page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded")
                typer.prompt("Press Enter after you are fully logged in", default="", show_default=False)

                raw_cookies = context.cookies("https://x.com")
                cookies = {item["name"]: item["value"] for item in raw_cookies}
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

    required = {"auth_token", "ct0"}
    if not required.issubset(cookies.keys()):
        raise RuntimeError(
            "Login appears incomplete: required X session cookies were not found. "
            "Confirm you are fully logged in and retry."
        )

    cookies_path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
    return cookies_path

from __future__ import annotations

from datetime import UTC, datetime
import subprocess
import sys
from typing import Any

from xs2n.agents.schemas import Post, Thread


NITTER_NET_BASE_URL = "https://nitter.net"
NITTER_PROFILE_TIMEOUT_MS = 30_000


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


def parse_nitter_datetime(value: str) -> datetime:
    normalized = " ".join(value.replace("\xa0", " ").split())
    normalized = normalized.replace(" · ", " ")
    if normalized.endswith(" UTC"):
        normalized = f"{normalized[:-4]} +0000"
    parsed = datetime.strptime(normalized, "%b %d, %Y %I:%M %p %z")
    return parsed.astimezone(UTC)


def _status_url_to_x_url(*, author_handle: str, post_id: str) -> str:
    return f"https://x.com/{author_handle}/status/{post_id}"


def build_threads_from_nitter_profile_items(
    account_handle: str,
    profile_items: list[dict[str, str]],
) -> list[Thread]:
    threads: list[Thread] = []
    for item in profile_items:
        post_id = item.get("post_id", "").strip()
        author_handle = item.get("author_handle", "").strip() or account_handle
        created_at_value = item.get("created_at", "").strip()
        if not post_id or not created_at_value:
            continue

        post = Post(
            post_id=post_id,
            author_handle=author_handle,
            created_at=parse_nitter_datetime(created_at_value),
            text=item.get("text", ""),
            url=_status_url_to_x_url(author_handle=author_handle, post_id=post_id),
        )
        threads.append(
            Thread(
                thread_id=post.post_id,
                account_handle=account_handle,
                posts=[post],
            )
        )
    return threads


def _scrape_items_from_page(page: Any) -> list[dict[str, str]]:
    return page.evaluate(
        """() => {
            const absoluteUrl = (href) => {
              try {
                return new URL(href, window.location.origin).href;
              } catch {
                return "";
              }
            };

            return Array.from(document.querySelectorAll(".timeline .timeline-item")).map((item) => {
              const link = item.querySelector(".tweet-link");
              const dateLink = item.querySelector(".tweet-date a");
              const textNode = item.querySelector(".tweet-content");
              const usernameNode = item.querySelector(".username");
              const href = link ? absoluteUrl(link.getAttribute("href") || "") : "";
              const statusMatch = href.match(/\\/status\\/(\\d+)/);
              const usernameText = usernameNode ? usernameNode.textContent || "" : "";

              return {
                post_id: statusMatch ? statusMatch[1] : "",
                author_handle: usernameText.replace(/^@/, "").trim() || item.dataset.username || "",
                created_at: dateLink ? (dateLink.getAttribute("title") || "").trim() : "",
                text: textNode ? (textNode.textContent || "").trim() : "",
                url: href,
              };
            }).filter((item) => item.post_id && item.author_handle && item.created_at);
        }"""
    )


def _launch_nitter_browser(playwright: Any, *, headless: bool) -> Any:
    return playwright.chromium.launch(headless=headless)


def scrape_nitter_profile_items(handle: str) -> list[dict[str, str]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError(
            "Playwright dependency is missing in this environment. Run `uv sync` and retry."
        ) from error

    page_url = f"{NITTER_NET_BASE_URL}/{handle}"

    for attempt in range(2):
        try:
            with sync_playwright() as playwright:
                for headless in (True, False):
                    browser = _launch_nitter_browser(playwright, headless=headless)
                    try:
                        page = browser.new_page()
                        response = page.goto(
                            page_url,
                            timeout=NITTER_PROFILE_TIMEOUT_MS,
                            wait_until="domcontentloaded",
                        )
                        if response is not None and response.status >= 400:
                            raise RuntimeError(
                                f"nitter.net returned HTTP {response.status} for @{handle}."
                            )

                        try:
                            page.wait_for_load_state("networkidle", timeout=5_000)
                        except Exception:
                            pass

                        items = _scrape_items_from_page(page)
                        if items:
                            return items
                    finally:
                        browser.close()
        except Exception as error:
            if attempt == 0 and is_missing_playwright_browser_error(error):
                install_playwright_chromium()
                continue
            raise RuntimeError(f"Could not scrape nitter.net for @{handle}: {error}") from error

    raise RuntimeError(f"Could not scrape nitter.net for @{handle}.")


def get_nitter_net_threads(*, handles: list[str], since_date: datetime) -> list[Thread]:
    threads: list[Thread] = []
    for handle in handles:
        profile_items = scrape_nitter_profile_items(handle)
        for thread in build_threads_from_nitter_profile_items(handle, profile_items):
            if thread.primary_post.created_at < since_date:
                continue
            threads.append(thread)
    return threads

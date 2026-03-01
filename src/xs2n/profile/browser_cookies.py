from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Callable

from twikit import Client


_REQUIRED_X_COOKIES = {"auth_token", "ct0"}
_CANDIDATE_DOMAINS = ("x.com", "twitter.com")
_CANDIDATE_BROWSERS = (
    "chrome",
    "chromium",
    "brave",
    "edge",
    "firefox",
    "safari",
    "opera",
    "opera_gx",
    "vivaldi",
)
_KEYCHAIN_HINT_SHOWN = False
_KEYCHAIN_HINT_MESSAGE = (
    "Hint: macOS may ask Keychain permission to access browser login data."
)


@dataclass
class BrowserCookieCandidate:
    browser_name: str
    domain: str
    cookies: dict[str, str]
    screen_name: str | None = None


def maybe_warn_keychain_prompt(echo: Callable[[str], None] | None = None) -> None:
    global _KEYCHAIN_HINT_SHOWN
    if _KEYCHAIN_HINT_SHOWN:
        return
    _KEYCHAIN_HINT_SHOWN = True
    if echo is None:
        print(_KEYCHAIN_HINT_MESSAGE)
        return
    echo(_KEYCHAIN_HINT_MESSAGE)


def _extract_cookie_values(cookie_jar: CookieJar) -> dict[str, str]:
    return {cookie.name: cookie.value for cookie in cookie_jar}


def _iter_cookie_loaders() -> list[tuple[str, Callable[..., CookieJar]]]:
    import browser_cookie3

    loaders: list[tuple[str, Callable[..., CookieJar]]] = []
    for browser_name in _CANDIDATE_BROWSERS:
        loader = getattr(browser_cookie3, browser_name, None)
        if callable(loader):
            loaders.append((browser_name, loader))
    return loaders


def _resolve_screen_name_from_cookies(cookies: dict[str, str]) -> str | None:
    client = Client("en-US")
    client.set_cookies(cookies)
    try:
        user = asyncio.run(client.user())
    except Exception:
        return None

    screen_name = getattr(user, "screen_name", None)
    if isinstance(screen_name, str) and screen_name:
        return screen_name
    return None


def resolve_screen_name_from_cookies(cookies: dict[str, str]) -> str | None:
    return _resolve_screen_name_from_cookies(cookies)


def discover_x_cookie_candidates(resolve_profiles: bool = True) -> list[BrowserCookieCandidate]:
    errors: list[str] = []
    candidates: list[BrowserCookieCandidate] = []
    seen_sessions: set[tuple[str, str]] = set()

    for browser_name, loader in _iter_cookie_loaders():
        for domain in _CANDIDATE_DOMAINS:
            try:
                cookies = _extract_cookie_values(loader(domain_name=domain))
            except Exception as error:  # pragma: no cover - environment-dependent
                errors.append(f"{browser_name}/{domain}: {error}")
                continue

            if not _REQUIRED_X_COOKIES.issubset(cookies.keys()):
                continue

            session_key = (cookies["auth_token"], cookies["ct0"])
            if session_key in seen_sessions:
                continue
            seen_sessions.add(session_key)

            screen_name = _resolve_screen_name_from_cookies(cookies) if resolve_profiles else None
            candidates.append(
                BrowserCookieCandidate(
                    browser_name=browser_name,
                    domain=domain,
                    cookies=cookies,
                    screen_name=screen_name,
                )
            )

    if candidates:
        return candidates

    details = "; ".join(errors[:4]) if errors else "no supported browser profile found"
    raise RuntimeError(
        "Could not find a logged-in X session in local browser cookies. "
        f"Tried domains x.com/twitter.com. Details: {details}"
    )


def describe_cookie_candidate(candidate: BrowserCookieCandidate) -> str:
    if candidate.screen_name:
        return f"@{candidate.screen_name} via {candidate.browser_name} ({candidate.domain})"
    return f"{candidate.browser_name} ({candidate.domain})"


def write_cookie_candidate(candidate: BrowserCookieCandidate, cookies_file: Path) -> Path:
    cookies_path = cookies_file.expanduser().resolve()
    cookies_path.parent.mkdir(parents=True, exist_ok=True)
    cookies_path.write_text(json.dumps(candidate.cookies, indent=2), encoding="utf-8")
    return cookies_path


def load_x_cookies_from_installed_browser() -> dict[str, str]:
    candidates = discover_x_cookie_candidates(resolve_profiles=False)
    return candidates[0].cookies


def bootstrap_cookies_from_local_browser(cookies_file: Path) -> Path:
    candidates = discover_x_cookie_candidates(resolve_profiles=False)
    return write_cookie_candidate(candidates[0], cookies_file)

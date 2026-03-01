from __future__ import annotations

import json
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Callable


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


def load_x_cookies_from_installed_browser() -> dict[str, str]:
    errors: list[str] = []
    for browser_name, loader in _iter_cookie_loaders():
        for domain in _CANDIDATE_DOMAINS:
            try:
                cookies = _extract_cookie_values(loader(domain_name=domain))
            except Exception as error:  # pragma: no cover - environment-dependent
                errors.append(f"{browser_name}/{domain}: {error}")
                continue

            if _REQUIRED_X_COOKIES.issubset(cookies.keys()):
                return cookies

    details = "; ".join(errors[:4]) if errors else "no supported browser profile found"
    raise RuntimeError(
        "Could not find a logged-in X session in local browser cookies. "
        f"Tried domains x.com/twitter.com. Details: {details}"
    )


def bootstrap_cookies_from_local_browser(cookies_file: Path) -> Path:
    cookies_path = cookies_file.expanduser().resolve()
    cookies_path.parent.mkdir(parents=True, exist_ok=True)

    cookies = load_x_cookies_from_installed_browser()
    cookies_path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
    return cookies_path

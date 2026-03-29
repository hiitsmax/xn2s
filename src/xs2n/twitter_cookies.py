from __future__ import annotations

import json
import os
from http.cookiejar import CookieJar
from pathlib import Path

import browser_cookie3


TWITTER_COOKIES_ENV_VAR = "TWITTER_COOKIES"
TWITTER_COOKIES_FILE_ENV_VAR = "TWITTER_COOKIES_FILE"


def get_chrome_cookie_files() -> list[Path]:
    chrome_root = (
        Path.home()
        / "Library"
        / "Application Support"
        / "Google"
        / "Chrome"
    )
    if not chrome_root.exists():
        return []

    cookie_files: list[Path] = []
    default_cookies = chrome_root / "Default" / "Cookies"
    if default_cookies.is_file():
        cookie_files.append(default_cookies)

    for profile_dir in sorted(chrome_root.iterdir()):
        if not profile_dir.is_dir() or profile_dir.name == "Default":
            continue
        cookie_file = profile_dir / "Cookies"
        if cookie_file.is_file():
            cookie_files.append(cookie_file)

    return cookie_files


def _cookiejar_to_map(cookiejar: CookieJar) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for cookie in cookiejar:
        if cookie.name and cookie.value:
            cookies[cookie.name] = cookie.value
    return cookies


def _parse_cookie_string(value: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for raw_part in value.split(";"):
        part = raw_part.strip()
        if not part or "=" not in part:
            continue
        key, cookie_value = part.split("=", 1)
        key = key.strip()
        cookie_value = cookie_value.strip()
        if key and cookie_value:
            cookies[key] = cookie_value
    return cookies


def _normalize_cookie_input(raw_value: str | dict[str, str] | None) -> str | None:
    if raw_value is None:
        return None

    if isinstance(raw_value, dict):
        cookies = {key: str(value) for key, value in raw_value.items() if value}
    else:
        candidate = raw_value.strip()
        if not candidate:
            return None
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            cookies = _parse_cookie_string(candidate)
        else:
            if not isinstance(parsed, dict):
                return None
            cookies = {key: str(value) for key, value in parsed.items() if value}

    if "auth_token" not in cookies or "ct0" not in cookies:
        return None

    ordered_keys = ["auth_token", "ct0"] + sorted(
        key for key in cookies if key not in {"auth_token", "ct0"}
    )
    return "; ".join(f"{key}={cookies[key]}" for key in ordered_keys)


def _load_cookies_from_cookie_file(cookie_file: Path) -> str | None:
    key_file = cookie_file.parent.parent / "Local State"
    merged_cookies: dict[str, str] = {}

    for domain_name in ("x.com", "twitter.com"):
        try:
            cookiejar = browser_cookie3.chrome(
                cookie_file=str(cookie_file),
                domain_name=domain_name,
                key_file=str(key_file) if key_file.exists() else None,
            )
        except Exception:
            return None
        merged_cookies.update(_cookiejar_to_map(cookiejar))

    return _normalize_cookie_input(merged_cookies)


def _load_cookies_from_chrome() -> str | None:
    for cookie_file in get_chrome_cookie_files():
        cookies = _load_cookies_from_cookie_file(cookie_file)
        if cookies is not None:
            return cookies
    return None


def _load_cookies_from_env() -> str | None:
    return _normalize_cookie_input(os.environ.get(TWITTER_COOKIES_ENV_VAR))


def _load_cookies_from_file() -> str | None:
    cookie_file = _read_cookie_file_path()
    if cookie_file is None or not cookie_file.is_file():
        return None
    return _normalize_cookie_input(cookie_file.read_text(encoding="utf-8"))


def _read_cookie_file_path() -> Path | None:
    raw_value = os.environ.get(TWITTER_COOKIES_FILE_ENV_VAR, "").strip()
    return Path(raw_value) if raw_value else None


def resolve_twitter_cookies() -> str:
    first_chrome_attempt = _load_cookies_from_chrome()
    if first_chrome_attempt is not None:
        return first_chrome_attempt

    env_cookies = _load_cookies_from_env()
    if env_cookies is not None:
        return env_cookies

    file_cookies = _load_cookies_from_file()
    if file_cookies is not None:
        return file_cookies

    second_chrome_attempt = _load_cookies_from_chrome()
    if second_chrome_attempt is not None:
        return second_chrome_attempt

    raise RuntimeError(
        "Could not find usable Twitter/X cookies in Chrome, TWITTER_COOKIES, or TWITTER_COOKIES_FILE."
    )

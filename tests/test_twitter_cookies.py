from __future__ import annotations

from http.cookiejar import Cookie, CookieJar
from pathlib import Path

import xs2n.twitter_cookies as twitter_cookies


def _cookie(name: str, value: str) -> Cookie:
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain="x.com",
        domain_specified=True,
        domain_initial_dot=False,
        path="/",
        path_specified=True,
        secure=False,
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )


def test_get_chrome_cookie_files_keeps_default_first(tmp_path: Path, monkeypatch) -> None:
    chrome_root = (
        tmp_path / "Library" / "Application Support" / "Google" / "Chrome"
    )
    (chrome_root / "Default").mkdir(parents=True)
    (chrome_root / "Profile 1").mkdir()
    (chrome_root / "Default" / "Cookies").write_text("", encoding="utf-8")
    (chrome_root / "Profile 1" / "Cookies").write_text("", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    cookie_files = twitter_cookies.get_chrome_cookie_files()

    assert cookie_files == [
        chrome_root / "Default" / "Cookies",
        chrome_root / "Profile 1" / "Cookies",
    ]


def test_normalize_cookie_input_accepts_header_or_json() -> None:
    header_value = twitter_cookies._normalize_cookie_input("auth_token=a; ct0=b; foo=c")
    json_value = twitter_cookies._normalize_cookie_input('{"auth_token":"a","ct0":"b"}')

    assert header_value == "auth_token=a; ct0=b; foo=c"
    assert json_value == "auth_token=a; ct0=b"


def test_cookiejar_to_map_keeps_cookie_values() -> None:
    jar = CookieJar()
    jar.set_cookie(_cookie("auth_token", "token"))
    jar.set_cookie(_cookie("ct0", "csrf"))

    assert twitter_cookies._cookiejar_to_map(jar) == {
        "auth_token": "token",
        "ct0": "csrf",
    }


def test_resolve_twitter_cookies_uses_env_before_file(monkeypatch, tmp_path: Path) -> None:
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("auth_token=file; ct0=file", encoding="utf-8")

    monkeypatch.setattr(twitter_cookies, "_load_cookies_from_chrome", lambda: None)
    monkeypatch.setenv("TWITTER_COOKIES", "auth_token=env; ct0=env")
    monkeypatch.setenv("TWITTER_COOKIES_FILE", str(cookie_file))

    assert twitter_cookies.resolve_twitter_cookies() == "auth_token=env; ct0=env"

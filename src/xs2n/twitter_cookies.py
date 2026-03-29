"""
AI-generated: This module was created with the assistance of an AI pair programmer.

Extract X (Twitter) session cookies from the local Chrome browser profile.

Purpose:
    Provide authenticated HTTP sessions for the X internal API by reading the
    ``auth_token`` and ``ct0`` cookies that Chrome stores after a normal login
    at x.com.  No separate credentials or API keys are required beyond having
    X open in Chrome.

Pre-conditions:
    - Chrome must be installed and the user must be logged in to x.com.
    - ``browser-cookie3`` must be installed (it is a declared project dependency).
Constraints / limitations:
    - On macOS, Chrome's cookie store is protected by the Keychain; the process
      must run as the same user that owns the Chrome profile.
    - Cookie values expire when the X session expires; re-login in Chrome
      refreshes them automatically.
    - Only Chrome is supported here.  Add other browsers by following the same
      pattern with ``browser_cookie3.firefox`` etc.
"""

from __future__ import annotations

import browser_cookie3


# Cookies required to authenticate against the X internal API.
_REQUIRED_COOKIE_NAMES = frozenset({"auth_token", "ct0"})


class XCookiesMissing(RuntimeError):
    """Raised when one or more required X cookies are absent from Chrome."""


def get_chrome_x_cookies() -> dict[str, str]:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Read the X session cookies from the Chrome cookie store.

    Uses ``browser_cookie3`` to open Chrome's SQLite cookie database and
    extract the cookies scoped to ``.x.com``.  The returned dict always
    contains both ``auth_token`` and ``ct0``; if either is missing the
    function raises rather than returning an incomplete set, because an
    incomplete set would silently produce 401/403 API errors.

    :returns: Dict with at least ``{"auth_token": ..., "ct0": ...}``.
    :raises XCookiesMissing: If Chrome has no valid X session (either the
        user is not logged in or the cookie store is inaccessible).

    Pre-conditions: Chrome is installed and the user is logged in to x.com.
    Post-conditions: Both ``auth_token`` and ``ct0`` are present in the
        returned dict.
    """
    # browser_cookie3 returns a RequestsCookieJar; iterate to build a plain dict
    jar = browser_cookie3.chrome(domain_name=".x.com")
    cookies = {c.name: c.value for c in jar}

    # Fail fast with a clear message rather than propagating confusing 401s
    missing = _REQUIRED_COOKIE_NAMES - cookies.keys()
    if missing:
        raise XCookiesMissing(
            f"Required X cookies not found in Chrome: {sorted(missing)}. "
            "Make sure you are logged in to x.com in Chrome."
        )

    return {name: cookies[name] for name in _REQUIRED_COOKIE_NAMES}

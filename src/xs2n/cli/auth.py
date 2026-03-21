from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import typer

from xs2n.profile.browser_cookies import (
    describe_cookie_candidate,
    discover_x_cookie_candidates,
    maybe_warn_keychain_prompt,
    resolve_screen_name_from_cookies,
    write_cookie_candidate,
)
from xs2n.profile.playwright import bootstrap_cookies_via_browser
from xs2n.schemas.auth import (
    AuthDoctorResult,
    ProviderStatus,
    RunReadiness,
    extract_valid_x_session_cookies,
)

auth_app = typer.Typer(
    help="Authentication helpers for digest and X session setup.",
    no_args_is_help=True,
)
x_app = typer.Typer(
    help="Manage X session cookies used by authenticated timeline commands.",
    no_args_is_help=True,
)
auth_app.add_typer(x_app, name="x")

_DEFAULT_CODEX_HOME = Path("~/.codex").expanduser()
_DEFAULT_CODEX_AUTH_PATH = Path("auth.json")


def _load_cookie_document(cookies_file: Path) -> dict[str, str] | None:
    if not cookies_file.exists():
        return None
    try:
        payload = json.loads(cookies_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return extract_valid_x_session_cookies(payload)


def _resolve_codex_home() -> Path:
    configured = os.getenv("CODEX_HOME")
    candidate = Path(configured).expanduser() if configured else _DEFAULT_CODEX_HOME
    try:
        return candidate.resolve()
    except OSError:
        return candidate


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _extract_access_token(document: dict[str, Any] | None) -> str | None:
    if not isinstance(document, dict):
        return None
    tokens = document.get("tokens")
    if not isinstance(tokens, dict):
        return None
    access_token = tokens.get("access_token")
    if not isinstance(access_token, str):
        return None
    return access_token.strip() or None


def _compute_codex_keychain_account(codex_home: Path) -> str:
    digest = hashlib.sha256(str(codex_home).encode("utf-8")).hexdigest()
    return f"cli|{digest[:16]}"


def _read_codex_keychain_auth(codex_home: Path) -> dict[str, Any] | None:
    if sys.platform != "darwin":
        return None

    account = _compute_codex_keychain_account(codex_home)
    try:
        completed = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                "Codex Auth",
                "-a",
                account,
                "-w",
            ],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None

    if completed.returncode != 0:
        return None

    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _resolve_codex_source() -> str | None:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if api_key:
        return "openai_api_key"

    codex_home = _resolve_codex_home()
    auth_document = _load_json(codex_home / _DEFAULT_CODEX_AUTH_PATH)
    if _extract_access_token(auth_document):
        return "codex_auth_file"

    keychain_document = _read_codex_keychain_auth(codex_home)
    if _extract_access_token(keychain_document):
        return "codex_auth_keychain"

    return None


def _build_codex_status(codex_bin: str) -> ProviderStatus:
    source = _resolve_codex_source()
    if source is None:
        return ProviderStatus(
            status="missing",
            summary="Codex credentials are missing.",
            detail=(
                "Run "
                f"`{codex_bin} login` or export `OPENAI_API_KEY`, then retry."
            ),
        )

    return ProviderStatus(
        status="ready",
        summary="Codex credentials available.",
        detail=f"Source: {source}",
    )


def _build_x_status(cookies_file: Path) -> ProviderStatus:
    resolved_path = cookies_file.expanduser().resolve()
    cookies = _load_cookie_document(resolved_path)
    if cookies is None:
        return ProviderStatus(
            status="missing",
            summary="X cookies file is missing required session cookies.",
            detail=str(resolved_path),
        )

    screen_name = resolve_screen_name_from_cookies(cookies)
    if screen_name:
        return ProviderStatus(
            status="ready",
            summary=f"X session ready for @{screen_name}.",
            detail=str(resolved_path),
        )

    return ProviderStatus(
        status="unverified",
        summary="X session cookies are present but could not be verified.",
        detail=str(resolved_path),
    )


def build_auth_doctor_result(
    *,
    cookies_file: Path,
    codex_bin: str,
) -> AuthDoctorResult:
    codex_status = _build_codex_status(codex_bin)
    x_status = _build_x_status(cookies_file)
    return AuthDoctorResult(
        codex=codex_status,
        x=x_status,
        run_readiness=RunReadiness(
            digest_ready=codex_status.status == "ready",
            latest_ready=(
                codex_status.status == "ready"
                and x_status.status == "ready"
            ),
        ),
    )


def login_x_session(*, cookies_file: Path) -> Path:
    maybe_warn_keychain_prompt(echo=typer.echo)
    try:
        candidates = discover_x_cookie_candidates(resolve_profiles=True)
    except RuntimeError:
        candidates = []

    if len(candidates) == 1:
        candidate = candidates[0]
        typer.echo(
            "Using logged-in browser session "
            f"{describe_cookie_candidate(candidate)}."
        )
        return write_cookie_candidate(candidate, cookies_file)

    if len(candidates) > 1:
        typer.echo(
            "Found multiple logged-in X browser sessions. "
            "Opening browser login to refresh the desired one explicitly."
        )

    return bootstrap_cookies_via_browser(cookies_file)


@auth_app.command("doctor")
def doctor(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable auth status output.",
    ),
    cookies_file: Path = typer.Option(
        Path("cookies.json"),
        "--cookies-file",
        help="Path where X session cookies are stored.",
    ),
    codex_bin: str = typer.Option(
        "codex",
        "--codex-bin",
        help="Codex CLI executable name/path for follow-up guidance.",
    ),
) -> AuthDoctorResult:
    snapshot = build_auth_doctor_result(
        cookies_file=cookies_file,
        codex_bin=codex_bin,
    )
    if json_output:
        typer.echo(snapshot.model_dump_json(indent=2))
        return snapshot

    typer.echo(f"Codex: {snapshot.codex.status} - {snapshot.codex.summary}")
    if snapshot.codex.detail:
        typer.echo(f"  {snapshot.codex.detail}")
    typer.echo(f"X: {snapshot.x.status} - {snapshot.x.summary}")
    if snapshot.x.detail:
        typer.echo(f"  {snapshot.x.detail}")
    typer.echo(
        "Run readiness: "
        f"digest={'yes' if snapshot.run_readiness.digest_ready else 'no'}, "
        f"latest={'yes' if snapshot.run_readiness.latest_ready else 'no'}"
    )
    return snapshot


@x_app.command("login")
def x_login(
    cookies_file: Path = typer.Option(
        Path("cookies.json"),
        "--cookies-file",
        help="Path where X session cookies should be saved.",
    ),
) -> Path:
    try:
        saved_path = login_x_session(cookies_file=cookies_file)
    except RuntimeError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Saved X session cookies to {saved_path}.")
    return saved_path


@x_app.command("reset")
def x_reset(
    cookies_file: Path = typer.Option(
        Path("cookies.json"),
        "--cookies-file",
        help="Path where X session cookies are stored.",
    ),
) -> Path | None:
    resolved_path = cookies_file.expanduser().resolve()
    if not resolved_path.exists():
        typer.echo(f"No X session cookies were stored at {resolved_path}.")
        return None

    resolved_path.unlink()
    typer.echo(f"Removed X session cookies at {resolved_path}.")
    return resolved_path

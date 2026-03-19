from __future__ import annotations

import os
from pathlib import Path
import plistlib
import shlex
import stat
import subprocess
import sys

from xs2n.ui.macos.app_menu import APP_NAME


BUNDLED_ENV_VAR = "XS2N_UI_BUNDLED"
BUNDLE_EXECUTABLE_NAME = "xn2s-ui"


def relaunch_ui_from_app_bundle(
    *,
    repo_root: Path,
    data_dir: Path,
    run_id: str | None,
) -> bool:
    if sys.platform != "darwin":
        return False
    if os.environ.get(BUNDLED_ENV_VAR) == "1":
        return False
    if _has_interactive_terminal():
        return False

    bundle_path = _ensure_ui_bundle(
        repo_root=repo_root,
        python_executable=Path(sys.executable),
    )
    command = ["open", "-na", str(bundle_path), "--args", "--data-dir", str(data_dir)]
    if run_id is not None:
        command.extend(["--run-id", run_id])

    subprocess.Popen(
        command,
        cwd=repo_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def _has_interactive_terminal() -> bool:
    return any(
        _stream_is_tty(stream)
        for stream in (sys.stdin, sys.stdout, sys.stderr)
    )


def _stream_is_tty(stream: object) -> bool:
    if stream is None or not hasattr(stream, "isatty"):
        return False

    try:
        return bool(stream.isatty())
    except OSError:
        return False


def _ensure_ui_bundle(*, repo_root: Path, python_executable: Path) -> Path:
    bundle_root = repo_root / "data" / ".ui_bundle" / f"{APP_NAME}.app"
    contents_dir = bundle_root / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"
    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    info_plist_path = contents_dir / "Info.plist"
    launcher_path = macos_dir / BUNDLE_EXECUTABLE_NAME

    info_plist_path.write_bytes(plistlib.dumps(_build_info_plist()))
    launcher_path.write_text(
        _build_launcher_script(
            repo_root=repo_root,
            python_executable=python_executable,
        ),
        encoding="utf-8",
    )
    launcher_path.chmod(
        launcher_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    return bundle_root


def _build_info_plist() -> dict[str, object]:
    return {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleDisplayName": APP_NAME,
        "CFBundleExecutable": BUNDLE_EXECUTABLE_NAME,
        "CFBundleIdentifier": "com.xn2s.ui",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": APP_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
    }


def _build_launcher_script(
    *,
    repo_root: Path,
    python_executable: Path,
) -> str:
    quoted_repo_root = shlex.quote(str(repo_root))
    quoted_python = shlex.quote(str(python_executable))
    return "\n".join(
        [
            "#!/bin/zsh",
            f"cd {quoted_repo_root}",
            f"export {BUNDLED_ENV_VAR}=1",
            f'exec {quoted_python} -m xs2n.cli.cli ui "$@"',
            "",
        ]
    )

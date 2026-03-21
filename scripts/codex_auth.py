from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from xs2n.codex_auth import (
    build_codex_login_command,
    build_codex_logout_command,
    build_codex_status_command,
    run_codex_command,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Minimal Codex authentication helper.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser("login", help="Log into Codex.")
    login_parser.add_argument(
        "--device-auth",
        action="store_true",
        help="Use Codex device-code auth flow for headless environments.",
    )
    subparsers.add_parser("status", help="Show Codex authentication status.")
    subparsers.add_parser("logout", help="Log out from Codex.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "login":
        command = build_codex_login_command(device_auth=bool(args.device_auth))
    elif args.command == "status":
        command = build_codex_status_command()
    else:
        command = build_codex_logout_command()

    try:
        return run_codex_command(command)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from dataclasses import dataclass

from xs2n.report_runtime import (
    DEFAULT_COOKIES_PATH,
    IssuesRunArguments as RuntimeIssuesRunArguments,
    LatestRunArguments as RuntimeLatestRunArguments,
    RunCommand as RuntimeRunCommand,
)


@dataclass(slots=True)
class RunCommand:
    label: str
    args: list[str]
    stream_jsonl_events: bool = False


def _ui_command(
    command: RuntimeRunCommand,
    *,
    stream_jsonl_events: bool = False,
) -> RunCommand:
    return RunCommand(
        label=command.label,
        args=command.args,
        stream_jsonl_events=stream_jsonl_events,
    )


class IssuesRunArguments(RuntimeIssuesRunArguments):
    def to_cli_args(self) -> list[str]:
        return [*super().to_cli_args(), "--jsonl-events"]

    def to_command(self) -> RunCommand:
        return _ui_command(
            RuntimeIssuesRunArguments.to_command(self),
            stream_jsonl_events=True,
        )


class LatestRunArguments(RuntimeLatestRunArguments):
    def to_cli_args(self) -> list[str]:
        args = super().to_cli_args()
        insert_at = len(args)
        for option_name in ("--since", "--home-latest"):
            if option_name in args:
                insert_at = min(insert_at, args.index(option_name))
        return [*args[:insert_at], "--jsonl-events", *args[insert_at:]]

    def to_command(self) -> RunCommand:
        return _ui_command(
            RuntimeLatestRunArguments.to_command(self),
            stream_jsonl_events=True,
        )

    def to_following_refresh_command(self) -> RunCommand:
        return _ui_command(RuntimeLatestRunArguments.to_following_refresh_command(self))


def __getattr__(name: str):
    if name == "DigestRunArguments":
        return IssuesRunArguments
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DEFAULT_COOKIES_PATH",
    "IssuesRunArguments",
    "LatestRunArguments",
    "RunCommand",
]

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from xs2n.profile.timeline import DEFAULT_IMPORT_TIMELINE
from xs2n.storage import DEFAULT_SOURCES_PATH, DEFAULT_TIMELINE_PATH


DEFAULT_COOKIES_PATH = Path("cookies.json")
DEFAULT_REPORT_RUNS_PATH = Path("data/report_runs")
DEFAULT_REPORT_MODEL = "gpt-5.4-mini"


@dataclass(slots=True)
class RunCommand:
    label: str
    args: list[str]


@dataclass(slots=True)
class IssuesRunArguments:
    timeline_file: Path = DEFAULT_TIMELINE_PATH
    output_dir: Path = DEFAULT_REPORT_RUNS_PATH
    model: str = DEFAULT_REPORT_MODEL

    @classmethod
    def from_form(
        cls,
        *,
        timeline_file: str | Path | None,
        output_dir: str | Path | None,
        model: str | None,
        taxonomy_file: str | Path | None = None,
        parallel_workers: str | int | None = None,
    ) -> IssuesRunArguments:
        return cls(
            timeline_file=_coerce_path(
                timeline_file,
                default=DEFAULT_TIMELINE_PATH,
            ),
            output_dir=_coerce_path(
                output_dir,
                default=DEFAULT_REPORT_RUNS_PATH,
            ),
            model=_coerce_text(model, default=DEFAULT_REPORT_MODEL),
        )

    def to_cli_args(self) -> list[str]:
        return [
            "report",
            "issues",
            "--timeline-file",
            str(self.timeline_file),
            "--output-dir",
            str(self.output_dir),
            "--model",
            self.model,
        ]

    def to_command(self) -> RunCommand:
        return RunCommand(label="report issues", args=self.to_cli_args())


DigestRunArguments = IssuesRunArguments


@dataclass(slots=True)
class LatestRunArguments:
    since: str | None = None
    lookback_hours: int = 24
    cookies_file: Path = DEFAULT_COOKIES_PATH
    limit: int = DEFAULT_IMPORT_TIMELINE
    timeline_file: Path = DEFAULT_TIMELINE_PATH
    sources_file: Path = DEFAULT_SOURCES_PATH
    home_latest: bool = False
    output_dir: Path = DEFAULT_REPORT_RUNS_PATH
    model: str = DEFAULT_REPORT_MODEL

    @classmethod
    def from_form(
        cls,
        *,
        since: str | None,
        lookback_hours: str | int | None,
        cookies_file: str | Path | None,
        limit: str | int | None,
        timeline_file: str | Path | None,
        sources_file: str | Path | None,
        home_latest: bool,
        output_dir: str | Path | None,
        model: str | None,
        taxonomy_file: str | Path | None = None,
        parallel_workers: str | int | None = None,
    ) -> LatestRunArguments:
        normalized_since = _coerce_optional_text(since)
        return cls(
            since=normalized_since,
            lookback_hours=_coerce_positive_int(
                lookback_hours,
                default=24,
                field_name="Lookback hours",
            ),
            cookies_file=_coerce_path(
                cookies_file,
                default=DEFAULT_COOKIES_PATH,
            ),
            limit=_coerce_positive_int(
                limit,
                default=DEFAULT_IMPORT_TIMELINE,
                field_name="Timeline limit",
            ),
            timeline_file=_coerce_path(
                timeline_file,
                default=DEFAULT_TIMELINE_PATH,
            ),
            sources_file=_coerce_path(
                sources_file,
                default=DEFAULT_SOURCES_PATH,
            ),
            home_latest=home_latest,
            output_dir=_coerce_path(
                output_dir,
                default=DEFAULT_REPORT_RUNS_PATH,
            ),
            model=_coerce_text(model, default=DEFAULT_REPORT_MODEL),
        )

    def to_cli_args(self) -> list[str]:
        args = [
            "report",
            "latest",
            "--lookback-hours",
            str(self.lookback_hours),
            "--cookies-file",
            str(self.cookies_file),
            "--limit",
            str(self.limit),
            "--timeline-file",
            str(self.timeline_file),
            "--sources-file",
            str(self.sources_file),
            "--output-dir",
            str(self.output_dir),
            "--model",
            self.model,
        ]
        if self.since is not None:
            args.extend(["--since", self.since])
        if self.home_latest:
            args.append("--home-latest")
        return args

    def to_command(self) -> RunCommand:
        return RunCommand(label="report latest", args=self.to_cli_args())

    def to_following_refresh_command(self) -> RunCommand:
        return RunCommand(
            label="refresh following sources",
            args=[
                "onboard",
                "--refresh-following",
                "--cookies-file",
                str(self.cookies_file),
                "--sources-file",
                str(self.sources_file),
            ],
        )

    def to_storage_doc(self) -> dict[str, object]:
        return {
            "since": self.since,
            "lookback_hours": self.lookback_hours,
            "cookies_file": str(self.cookies_file),
            "limit": self.limit,
            "timeline_file": str(self.timeline_file),
            "sources_file": str(self.sources_file),
            "home_latest": self.home_latest,
            "output_dir": str(self.output_dir),
            "model": self.model,
        }

    @classmethod
    def from_storage_doc(cls, doc: dict[str, object]) -> LatestRunArguments:
        return cls(
            since=doc.get("since") if isinstance(doc.get("since"), str) else None,
            lookback_hours=int(doc.get("lookback_hours", 24)),
            cookies_file=Path(str(doc.get("cookies_file", DEFAULT_COOKIES_PATH))),
            limit=int(doc.get("limit", DEFAULT_IMPORT_TIMELINE)),
            timeline_file=Path(str(doc.get("timeline_file", DEFAULT_TIMELINE_PATH))),
            sources_file=Path(str(doc.get("sources_file", DEFAULT_SOURCES_PATH))),
            home_latest=bool(doc.get("home_latest", False)),
            output_dir=Path(str(doc.get("output_dir", DEFAULT_REPORT_RUNS_PATH))),
            model=str(doc.get("model", DEFAULT_REPORT_MODEL)),
        )


def _coerce_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _coerce_text(value: str | None, *, default: str) -> str:
    normalized = _coerce_optional_text(value)
    return default if normalized is None else normalized


def _coerce_path(value: str | Path | None, *, default: Path) -> Path:
    if value is None:
        return default
    if isinstance(value, Path):
        return value
    normalized = value.strip()
    if not normalized:
        return default
    return Path(normalized)


def _coerce_positive_int(
    value: str | int | None,
    *,
    default: int,
    field_name: str,
) -> int:
    if value is None:
        return default

    if isinstance(value, int):
        normalized = value
    else:
        stripped = value.strip()
        if not stripped:
            return default
        try:
            normalized = int(stripped)
        except ValueError as error:
            raise ValueError(f"{field_name} must be a positive integer.") from error

    if normalized < 1:
        raise ValueError(f"{field_name} must be at least 1.")
    return normalized


__all__ = [
    "DEFAULT_COOKIES_PATH",
    "DigestRunArguments",
    "IssuesRunArguments",
    "LatestRunArguments",
    "RunCommand",
]

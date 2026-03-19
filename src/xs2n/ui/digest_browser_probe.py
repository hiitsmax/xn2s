from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from time import perf_counter

import fltk

from xs2n.ui.digest_browser import DigestBrowser


@dataclass(slots=True)
class DigestBrowserProbeResult:
    run_dir: str
    load_run_ms: float
    issue_count: int
    issue_timings_ms: list[float]
    selected_issue_titles: list[str]
    canvas_chars: int
    screenshot_path: str | None


def probe_digest_browser(
    *,
    run_dir: Path,
    screenshot_path: Path | None = None,
    issue_limit: int = 3,
) -> DigestBrowserProbeResult:
    window = fltk.Fl_Double_Window(1320, 920, "xs2n digest browser probe")
    window.begin()
    browser = DigestBrowser(
        x=0,
        y=0,
        width=1320,
        height=920,
        on_open_url=lambda _url: None,
    )
    window.end()
    window.show()
    browser.show()
    fltk.Fl.check()

    start = perf_counter()
    loaded = browser.load_run(run_dir)
    load_run_ms = round((perf_counter() - start) * 1000, 2)
    if not loaded:
        raise RuntimeError(f"Could not load digest preview from {run_dir}.")

    issue_timings_ms: list[float] = []
    selected_issue_titles: list[str] = []
    for selection_index, issue_row in enumerate(browser._issue_rows[:issue_limit], start=1):
        browser.issue_list.value(selection_index)
        start = perf_counter()
        browser._on_issue_selected(browser.issue_list)
        issue_timings_ms.append(round((perf_counter() - start) * 1000, 2))
        selected_issue_titles.append(issue_row.title)
        fltk.Fl.check()

    if screenshot_path is not None:
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        image = fltk.fl_capture_window(window, 0, 0, window.w(), window.h())
        write_result = fltk.fl_write_png(str(screenshot_path), image)
        if write_result != 0:
            raise RuntimeError(
                f"fl_write_png failed with exit code {write_result}."
            )

    canvas_chars = len(browser.issue_canvas_buffer.text() or "")
    window.hide()
    fltk.Fl.check()
    return DigestBrowserProbeResult(
        run_dir=str(run_dir),
        load_run_ms=load_run_ms,
        issue_count=len(browser._issue_rows),
        issue_timings_ms=issue_timings_ms,
        selected_issue_titles=selected_issue_titles,
        canvas_chars=canvas_chars,
        screenshot_path=str(screenshot_path) if screenshot_path is not None else None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe the native xs2n digest browser and optionally save a screenshot.",
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="Path to a saved run directory containing issues.json and issue_assignments.json.",
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        default=None,
        help="Optional PNG path where a captured window screenshot will be written.",
    )
    parser.add_argument(
        "--issue-limit",
        type=int,
        default=3,
        help="How many top-ranked issues to click during the probe.",
    )
    args = parser.parse_args()

    result = probe_digest_browser(
        run_dir=args.run_dir,
        screenshot_path=args.screenshot,
        issue_limit=max(1, args.issue_limit),
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path

import fltk

from xs2n.ui import app as app_module


@dataclass(slots=True)
class ArtifactBrowserProbeResult:
    data_dir: str
    selected_run_id: str
    selected_artifact_name: str
    digest_viewer_active: bool
    window_size: tuple[int, int]
    pane_widths: dict[str, int]
    screenshot_path: str | None


def probe_artifact_browser(
    *,
    data_dir: Path,
    run_id: str,
    artifact_name: str,
    width: int,
    height: int,
    screenshot_path: Path | None = None,
) -> ArtifactBrowserProbeResult:
    browser = app_module.ArtifactBrowserWindow(data_dir=data_dir)
    browser.window.show()
    fltk.Fl.check()
    browser.refresh_runs()
    fltk.Fl.check()

    run_index = next(
        (index for index, run in enumerate(browser.runs) if run.run_id == run_id),
        None,
    )
    if run_index is None:
        raise RuntimeError(f"Run {run_id!r} was not found under {data_dir}.")
    browser._apply_selected_run(run_index)
    fltk.Fl.check()

    browser._apply_selected_artifact_name(artifact_name, user_selected=True)
    fltk.Fl.check()

    _resize_artifact_browser_window(browser, width=width, height=height)
    fltk.Fl.check()

    if screenshot_path is not None:
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        image = fltk.fl_capture_window(
            browser.window,
            0,
            0,
            browser.window.w(),
            browser.window.h(),
        )
        write_result = fltk.fl_write_png(str(screenshot_path), image)
        if write_result != 0:
            raise RuntimeError(
                f"fl_write_png failed with exit code {write_result}."
            )

    result = ArtifactBrowserProbeResult(
        data_dir=str(data_dir),
        selected_run_id=browser.selected_run_id or "",
        selected_artifact_name=browser.selected_artifact_name or "",
        digest_viewer_active=browser._digest_viewer_active(),
        window_size=(browser.window.w(), browser.window.h()),
        pane_widths={
            "runs": browser.run_list_group.w(),
            "navigation": browser.navigation_group.w(),
            "viewer": browser.viewer.w(),
        },
        screenshot_path=str(screenshot_path) if screenshot_path is not None else None,
    )
    browser.window.hide()
    fltk.Fl.check()
    return result


def _resize_artifact_browser_window(
    browser: app_module.ArtifactBrowserWindow,
    *,
    width: int,
    height: int,
) -> None:
    window = browser.window
    tile_y = app_module.MENU_HEIGHT + app_module.COMMAND_HEIGHT
    tile_height = max(1, height - tile_y - app_module.STATUS_HEIGHT)
    button_y = app_module.MENU_HEIGHT + (
        app_module.COMMAND_HEIGHT - app_module.COMMAND_BUTTON_HEIGHT
    ) // 2
    primary_run_button_x = (
        app_module.COMMAND_STRIP_PADDING
        + app_module.COMMAND_BUTTON_WIDTH
        + app_module.COMMAND_BUTTON_GAP
    )
    focus_button_x = (
        width - app_module.COMMAND_STRIP_PADDING - app_module.COMMAND_BUTTON_WIDTH
    )

    window.resize(window.x(), window.y(), width, height)
    browser.menu_bar.resize(0, 0, width, app_module.MENU_HEIGHT)
    browser.command_strip.resize(
        0,
        app_module.MENU_HEIGHT,
        width,
        app_module.COMMAND_HEIGHT,
    )
    browser.refresh_button.resize(
        app_module.COMMAND_STRIP_PADDING,
        button_y,
        app_module.COMMAND_BUTTON_WIDTH,
        app_module.COMMAND_BUTTON_HEIGHT,
    )
    browser.run_latest_button.resize(
        primary_run_button_x,
        button_y,
        app_module.COMMAND_BUTTON_WIDTH,
        app_module.COMMAND_BUTTON_HEIGHT,
    )
    browser.focus_mode_button.resize(
        focus_button_x,
        button_y,
        app_module.COMMAND_BUTTON_WIDTH,
        app_module.COMMAND_BUTTON_HEIGHT,
    )
    browser.tile.resize(0, tile_y, width, tile_height)
    browser.status_output.resize(
        0,
        height - app_module.STATUS_HEIGHT,
        width,
        app_module.STATUS_HEIGHT,
    )

    if getattr(browser, "focus_mode_enabled", False):
        browser.viewer.resize(browser.tile.x(), browser.tile.y(), browser.tile.w(), browser.tile.h())
        if browser.digest_viewer is not None:
            browser.digest_viewer.resize(
                browser.tile.x(),
                browser.tile.y(),
                browser.tile.w(),
                browser.tile.h(),
            )
    else:
        browser._layout_standard_panes(
            left_pane_width=browser.run_list_group.w(),
            middle_pane_width=browser.navigation_group.w(),
        )
        browser._sync_digest_navigation_layout()
        browser._sync_run_list_layout(force=True)

    browser.tile.init_sizes()
    browser.tile.redraw()
    browser.window.redraw()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Open the native xs2n artifact browser, select a run and artifact, "
            "optionally resize the app window, and save a screenshot."
        ),
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory scanned by the artifact browser for report runs.",
    )
    parser.add_argument(
        "--run-id",
        required=True,
        help="Saved run id to select in the left pane.",
    )
    parser.add_argument(
        "--artifact-name",
        default="digest.html",
        help="Artifact to select after choosing the run.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=2000,
        help="Target app window width before capturing the screenshot.",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=1300,
        help="Target app window height before capturing the screenshot.",
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        default=None,
        help="Optional PNG path where the captured window screenshot will be written.",
    )
    args = parser.parse_args()

    result = probe_artifact_browser(
        data_dir=args.data_dir,
        run_id=args.run_id,
        artifact_name=args.artifact_name,
        width=max(1, args.width),
        height=max(1, args.height),
        screenshot_path=args.screenshot,
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()

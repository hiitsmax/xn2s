from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
import threading

import fltk

from xs2n.ui.artifacts import (
    DEFAULT_UI_DATA_PATH,
    ArtifactRecord,
    RunRecord,
    format_run_details,
    format_run_summary,
    list_run_artifacts,
    scan_runs,
)
from xs2n.ui.viewer import render_artifact_html, render_plain_text_html
from xs2n.ui.macos import APP_NAME, apply_macos_app_menu, prepare_macos_app_menu


WINDOW_WIDTH = 1480
WINDOW_HEIGHT = 920
MENU_HEIGHT = 30
COMMAND_HEIGHT = 40
STATUS_HEIGHT = 24
LEFT_PANE_WIDTH = 380
MIDDLE_PANE_WIDTH = 340
DETAILS_HEIGHT = 140


@dataclass(slots=True)
class CommandResult:
    label: str
    command: list[str]
    returncode: int
    output: str


class ArtifactBrowserWindow:
    def __init__(
        self,
        *,
        data_dir: Path,
        initial_run_id: str | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.initial_run_id = initial_run_id
        self.repo_root = Path(__file__).resolve().parents[3]
        self.cli_executable = self._resolve_cli_executable()
        self.command_results: Queue[CommandResult] = Queue()
        self.running_label: str | None = None
        self.running_thread: threading.Thread | None = None
        self.selected_run_id: str | None = initial_run_id
        self.selected_artifact_name: str | None = None
        self.runs: list[RunRecord] = []
        self.artifacts: list[ArtifactRecord] = []

        self.window = fltk.Fl_Double_Window(
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
            f"{APP_NAME} Artifact Browser",
        )
        self._build_window()
        self.refresh_runs()
        fltk.Fl.add_idle(self._drain_command_results)

    def show(self) -> None:
        prepare_macos_app_menu()
        self.window.show()
        apply_macos_app_menu(APP_NAME)

    def _build_window(self) -> None:
        tile_y = MENU_HEIGHT + COMMAND_HEIGHT
        tile_height = WINDOW_HEIGHT - tile_y - STATUS_HEIGHT
        right_pane_x = LEFT_PANE_WIDTH + MIDDLE_PANE_WIDTH
        right_pane_width = WINDOW_WIDTH - right_pane_x
        viewer_y = tile_y + DETAILS_HEIGHT
        viewer_height = tile_height - DETAILS_HEIGHT

        self.window.begin()

        self.menu_bar = fltk.Fl_Menu_Bar(0, 0, WINDOW_WIDTH, MENU_HEIGHT)
        self.menu_bar.add("&File/&Refresh", 0, self._on_refresh_clicked, None)
        self.menu_bar.add("&Run/&Digest", 0, self._on_run_digest_clicked, None)
        self.menu_bar.add(
            "&Run/&Latest 24h",
            0,
            self._on_run_latest_clicked,
            None,
        )
        self.menu_bar.add("&File/&Quit", 0, self._on_quit_clicked, None)

        self.refresh_button = fltk.Fl_Button(12, 36, 120, 28, "Refresh")
        self.refresh_button.callback(self._on_refresh_clicked, None)
        self.refresh_button.box(fltk.FL_THIN_UP_BOX)

        self.run_digest_button = fltk.Fl_Return_Button(
            144,
            36,
            148,
            28,
            "Run Digest",
        )
        self.run_digest_button.callback(self._on_run_digest_clicked, None)
        self.run_digest_button.box(fltk.FL_THIN_UP_BOX)

        self.run_latest_button = fltk.Fl_Button(
            304,
            36,
            168,
            28,
            "Run Latest 24h",
        )
        self.run_latest_button.callback(self._on_run_latest_clicked, None)
        self.run_latest_button.box(fltk.FL_THIN_UP_BOX)

        self.tile = fltk.Fl_Tile(0, tile_y, WINDOW_WIDTH, tile_height)
        self.tile.begin()

        self.runs_browser = fltk.Fl_Hold_Browser(
            0,
            tile_y,
            LEFT_PANE_WIDTH,
            tile_height,
            "Runs",
        )
        self._style_browser(self.runs_browser)
        self.runs_browser.callback(self._on_run_selected, None)

        self.artifacts_browser = fltk.Fl_Hold_Browser(
            LEFT_PANE_WIDTH,
            tile_y,
            MIDDLE_PANE_WIDTH,
            tile_height,
            "Artifacts",
        )
        self._style_browser(self.artifacts_browser)
        self.artifacts_browser.callback(self._on_artifact_selected, None)

        self.details_group = fltk.Fl_Group(
            right_pane_x,
            tile_y,
            right_pane_width,
            tile_height,
        )
        self.details_group.begin()

        self.run_details = fltk.Fl_Multiline_Output(
            right_pane_x,
            tile_y,
            right_pane_width,
            DETAILS_HEIGHT,
            "Run Details",
        )
        self.run_details.box(fltk.FL_BORDER_BOX)
        self.run_details.textfont(fltk.FL_COURIER)
        self.run_details.textsize(13)

        self.viewer = fltk.Fl_Help_View(
            right_pane_x,
            viewer_y,
            right_pane_width,
            viewer_height,
            "Viewer",
        )
        self.viewer.box(fltk.FL_BORDER_BOX)
        self.viewer.textfont(fltk.FL_HELVETICA)
        self.viewer.textsize(14)

        self.details_group.end()
        self.details_group.resizable(self.viewer)

        self.tile.end()

        self.status_output = fltk.Fl_Output(
            0,
            WINDOW_HEIGHT - STATUS_HEIGHT,
            WINDOW_WIDTH,
            STATUS_HEIGHT,
        )
        self.status_output.box(fltk.FL_FLAT_BOX)
        self.status_output.textfont(fltk.FL_HELVETICA)
        self.status_output.textsize(12)
        self.status_output.value(
            f"Ready. Browsing run artifacts under {self.data_dir}."
        )

        self.window.end()
        self.window.resizable(self.tile)
        self.window.callback(self._on_quit_clicked, None)

    def refresh_runs(self) -> None:
        self.runs = scan_runs(self.data_dir)
        self.runs_browser.clear()
        for run in self.runs:
            self.runs_browser.add(format_run_summary(run))

        if not self.runs:
            self.selected_run_id = None
            self.artifacts = []
            self.artifacts_browser.clear()
            self.run_details.value(
                f"No report runs found under {self.data_dir}.\n"
                "Run `xs2n report digest` or `xs2n report latest` to create one."
            )
            self._set_viewer_html(
                render_plain_text_html(
                    title="No Runs Discovered Yet",
                    body=(
                        "This browser scans every data/report_runs* directory "
                        "and reads whatever artifacts already exist on disk.\n\n"
                        "Run `xs2n report digest` or `xs2n report latest` to "
                        "create a run folder."
                    ),
                    metadata={"data_dir": str(self.data_dir)},
                )
            )
            self.status_output.value(
                f"No run folders found in {self.data_dir}."
            )
            return

        selected_index = self._resolve_selected_run_index()
        self.runs_browser.value(selected_index + 1)
        self._apply_selected_run(selected_index)

    def _resolve_selected_run_index(self) -> int:
        if self.selected_run_id is not None:
            for index, run in enumerate(self.runs):
                if run.run_id == self.selected_run_id:
                    return index
        return 0

    def _apply_selected_run(self, index: int) -> None:
        run = self.runs[index]
        self.selected_run_id = run.run_id
        self.run_details.value(format_run_details(run))

        self.artifacts = list_run_artifacts(run)
        self.artifacts_browser.clear()
        for artifact in self.artifacts:
            label = artifact.name
            if artifact.phase_name is not None:
                label = f"{label} [{artifact.phase_name}]"
            self.artifacts_browser.add(label)

        if not self.artifacts:
            self.selected_artifact_name = None
            self._set_viewer_html(
                render_plain_text_html(
                    title=f"{run.run_id} Has No Visible Artifacts Yet",
                    body="This run folder exists, but no inspectable artifacts were found.",
                    metadata={"run_id": run.run_id},
                )
            )
            return

        preferred_index = self._resolve_selected_artifact_index()
        self.artifacts_browser.value(preferred_index + 1)
        self._apply_selected_artifact(preferred_index)

    def _resolve_selected_artifact_index(self) -> int:
        if self.selected_artifact_name is not None:
            for index, artifact in enumerate(self.artifacts):
                if artifact.name == self.selected_artifact_name:
                    return index
        for index, artifact in enumerate(self.artifacts):
            if artifact.name == "digest.md":
                return index
        return 0

    def _apply_selected_artifact(self, index: int) -> None:
        artifact = self.artifacts[index]
        self.selected_artifact_name = artifact.name
        self._set_viewer_html(render_artifact_html(artifact))
        self.status_output.value(f"Viewing {artifact.name}.")

    def _start_command(self, *, label: str, args: list[str]) -> None:
        if self.running_thread is not None and self.running_thread.is_alive():
            fltk.fl_alert(
                f"`{self.running_label}` is still running. Wait for it to finish first."
            )
            return

        command = [self.cli_executable, *args]
        self.running_label = label
        self.status_output.value(f"Running {label}...")
        self._set_viewer_html(
            render_plain_text_html(
                title=f"Running {label}",
                body=f"$ {' '.join(command)}\n\nStarting background command...\n",
                metadata={"cwd": str(self.repo_root)},
            )
        )

        def worker() -> None:
            completed = subprocess.run(
                command,
                cwd=self.repo_root,
                text=True,
                capture_output=True,
                check=False,
            )
            transcript_parts = [f"$ {' '.join(command)}", ""]
            if completed.stdout:
                transcript_parts.extend(["stdout:", completed.stdout.rstrip(), ""])
            if completed.stderr:
                transcript_parts.extend(["stderr:", completed.stderr.rstrip(), ""])
            transcript_parts.append(f"exit_code: {completed.returncode}")
            self.command_results.put(
                CommandResult(
                    label=label,
                    command=command,
                    returncode=completed.returncode,
                    output="\n".join(transcript_parts).rstrip() + "\n",
                )
            )

        self.running_thread = threading.Thread(target=worker, daemon=True)
        self.running_thread.start()

    def _drain_command_results(self, _data=None) -> None:  # noqa: ANN001
        while True:
            try:
                result = self.command_results.get_nowait()
            except Empty:
                break

            self._set_viewer_html(
                render_plain_text_html(
                    title=result.label,
                    body=result.output,
                    metadata={"exit_code": str(result.returncode)},
                )
            )
            if result.returncode == 0:
                self.status_output.value(f"{result.label} finished successfully.")
            else:
                self.status_output.value(
                    f"{result.label} failed with exit code {result.returncode}."
                )
            self.running_label = None
            self.running_thread = None
            self.refresh_runs()

    def _on_refresh_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        self.refresh_runs()
        self.status_output.value("Run list refreshed.")

    def _on_run_digest_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        self._start_command(label="report digest", args=["report", "digest"])

    def _on_run_latest_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        self._start_command(
            label="report latest --lookback-hours 24",
            args=["report", "latest", "--lookback-hours", "24"],
        )

    def _on_quit_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        self.window.hide()

    def _on_run_selected(self, widget, data=None) -> None:  # noqa: ANN001
        selection = widget.value()
        if selection < 1 or selection > len(self.runs):
            return
        self._apply_selected_run(selection - 1)

    def _on_artifact_selected(self, widget, data=None) -> None:  # noqa: ANN001
        selection = widget.value()
        if selection < 1 or selection > len(self.artifacts):
            return
        self._apply_selected_artifact(selection - 1)

    def _resolve_cli_executable(self) -> str:
        argv0 = Path(sys.argv[0])
        if argv0.exists():
            return str(argv0.resolve())
        return "xs2n"

    def _set_viewer_html(self, html: str) -> None:
        self.viewer.value(html)
        self.viewer.topline(0)
        self.viewer.leftline(0)

    @staticmethod
    def _style_browser(browser) -> None:  # noqa: ANN001
        browser.box(fltk.FL_BORDER_BOX)
        browser.textfont(fltk.FL_HELVETICA)
        browser.textsize(14)


def run_artifact_browser(
    *,
    data_dir: Path = DEFAULT_UI_DATA_PATH,
    initial_run_id: str | None = None,
) -> None:
    browser = ArtifactBrowserWindow(
        data_dir=data_dir,
        initial_run_id=initial_run_id,
    )
    browser.show()
    fltk.Fl.run()

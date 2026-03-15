from __future__ import annotations

from pathlib import Path
import sys

import typer
from typer.models import OptionInfo

from xs2n.ui import DEFAULT_UI_DATA_PATH


def _load_ui_launcher():
    from xs2n.ui.app import run_artifact_browser

    return run_artifact_browser


def ui(
    data_dir: Path = typer.Option(
        DEFAULT_UI_DATA_PATH,
        "--data-dir",
        help="Directory containing report_runs* artifact roots.",
    ),
    run_id: str | None = typer.Option(
        None,
        "--run-id",
        help="Run id to select when the browser opens.",
    ),
) -> None:
    """Open the desktop artifact browser."""

    resolved_data_dir = (
        DEFAULT_UI_DATA_PATH
        if isinstance(data_dir, OptionInfo)
        else data_dir
    )
    resolved_run_id = None if isinstance(run_id, OptionInfo) else run_id

    try:
        launch_browser = _load_ui_launcher()
    except ImportError as error:
        install_lines = [
            "The desktop UI dependencies are not ready.",
            "Install them with `uv sync --extra gui` and retry.",
        ]
        if sys.platform == "darwin":
            install_lines.append(
                "On macOS you may also need `brew install fltk` for the native FLTK runtime."
            )
        typer.echo("\n".join(install_lines), err=True)
        raise typer.Exit(code=1) from error

    launch_browser(
        data_dir=resolved_data_dir,
        initial_run_id=resolved_run_id,
    )

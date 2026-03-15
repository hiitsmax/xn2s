from __future__ import annotations

import typer

from xs2n.cli.onboard import onboard
from xs2n.cli.report import report_app
from xs2n.cli.timeline import timeline
from xs2n.cli.ui import ui

app = typer.Typer(help="xs2n CLI", no_args_is_help=True)


@app.callback()
def main() -> None:
    """xs2n command group."""


app.command("onboard")(onboard)
app.command("timeline")(timeline)
app.command("ui")(ui)
app.add_typer(report_app, name="report")


if __name__ == "__main__":
    app()

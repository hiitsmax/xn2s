from __future__ import annotations

import typer

from xs2n.cli.onboard import onboard

app = typer.Typer(help="xs2n CLI", no_args_is_help=True)


@app.callback()
def main() -> None:
    """xs2n command group."""


app.command("onboard")(onboard)


if __name__ == "__main__":
    app()

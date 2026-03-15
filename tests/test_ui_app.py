from __future__ import annotations

from types import SimpleNamespace
import signal

import xs2n.ui.app as app


def test_run_browser_event_loop_closes_browser_on_sigint(
    monkeypatch,
) -> None:
    idle_callbacks = []
    installed_handlers: list[object] = []
    previous_sigint_handler = object()
    close_calls: list[str] = []

    def fake_getsignal(signum: signal.Signals) -> object:
        assert signum is signal.SIGINT
        return previous_sigint_handler

    def fake_signal(signum: signal.Signals, handler: object) -> None:
        assert signum is signal.SIGINT
        installed_handlers.append(handler)

    class FakeFl:
        @staticmethod
        def add_idle(callback) -> None:  # noqa: ANN001
            idle_callbacks.append(callback)

        @staticmethod
        def remove_idle(callback) -> None:  # noqa: ANN001
            assert callback is idle_callbacks[0]

        @staticmethod
        def run() -> None:
            installed_handlers[0](signal.SIGINT, None)
            idle_callbacks[0](None)

    monkeypatch.setattr(app.signal, "getsignal", fake_getsignal)
    monkeypatch.setattr(app.signal, "signal", fake_signal)
    monkeypatch.setattr(app, "fltk", SimpleNamespace(Fl=FakeFl))

    app._run_browser_event_loop(
        close_browser=lambda: close_calls.append("closed"),
    )

    assert close_calls == ["closed"]
    assert installed_handlers == [installed_handlers[0], previous_sigint_handler]

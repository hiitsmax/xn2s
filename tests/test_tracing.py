from __future__ import annotations

import xs2n.utils.tracing as tracing_module


def test_configure_phoenix_tracing_registers_local_phoenix_defaults(
    monkeypatch,
) -> None:  # noqa: ANN001
    calls: dict[str, object] = {}

    monkeypatch.delenv("XS2N_DISABLE_TRACING", raising=False)
    monkeypatch.delenv("PHOENIX_COLLECTOR_ENDPOINT", raising=False)
    monkeypatch.delenv("PHOENIX_PROJECT_NAME", raising=False)
    monkeypatch.setattr(tracing_module, "_TRACING_CONFIGURED", False)

    def fake_register(**kwargs: object) -> object:
        calls["register"] = kwargs
        return object()

    configured = tracing_module.configure_phoenix_tracing(register_phoenix=fake_register)

    assert configured is True
    assert calls["register"] == {
        "endpoint": tracing_module.DEFAULT_PHOENIX_COLLECTOR_ENDPOINT,
        "project_name": tracing_module.DEFAULT_PHOENIX_PROJECT_NAME,
        "protocol": "http/protobuf",
        "verbose": False,
        "auto_instrument": True,
    }
    assert (
        tracing_module.os.environ["PHOENIX_COLLECTOR_ENDPOINT"]
        == tracing_module.DEFAULT_PHOENIX_COLLECTOR_ENDPOINT
    )


def test_configure_phoenix_tracing_honors_disable_flag(
    monkeypatch,
) -> None:  # noqa: ANN001
    monkeypatch.setenv("XS2N_DISABLE_TRACING", "1")
    monkeypatch.setattr(tracing_module, "_TRACING_CONFIGURED", False)

    configured = tracing_module.configure_phoenix_tracing(
        register_phoenix=lambda **_: (_ for _ in ()).throw(AssertionError("should not register"))
    )

    assert configured is False

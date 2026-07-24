"""Tests for the market-helm-web console entrypoint."""

from unittest.mock import patch


def test_dashboard_cli_passes_env_to_uvicorn(monkeypatch) -> None:
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("UVICORN_RELOAD", "yes")

    with patch("uvicorn.run") as run:
        from dashboard.backend.dashboard_cli import main

        main()

    run.assert_called_once_with(
        "dashboard.backend.main:app",
        host="127.0.0.1",
        port=9000,
        reload=True,
    )


def test_dashboard_cli_defaults_and_reload_false(monkeypatch) -> None:
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setenv("UVICORN_RELOAD", "no")

    with patch("uvicorn.run") as run:
        from dashboard.backend.dashboard_cli import main

        main()

    run.assert_called_once_with(
        "dashboard.backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )

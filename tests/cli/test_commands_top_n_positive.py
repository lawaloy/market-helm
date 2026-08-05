"""CLI --top-n must reject non-positive values before ranking slices invert."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.parametrize("value", ["0", "-1", "-50"])
def test_main_rejects_non_positive_top_n(value, monkeypatch):
    monkeypatch.setattr("sys.argv", ["market-helm", "--top-n", value])

    with patch("src.cli.commands.StockTrackerWorkflow") as ctor:
        with patch("src.cli.commands.display_results"):
            from src.cli.commands import main

            with pytest.raises(SystemExit) as excinfo:
                main()

    assert excinfo.value.code == 2
    ctor.assert_not_called()


def test_main_accepts_positive_top_n(monkeypatch):
    monkeypatch.setattr("sys.argv", ["market-helm", "--top-n", "7"])
    workflow = MagicMock()
    workflow.run.return_value = {"success": True, "analysis": {}, "metadata": {}}

    with patch("src.cli.commands.StockTrackerWorkflow", return_value=workflow):
        with patch("src.cli.commands.display_results"):
            from src.cli.commands import main

            main()

    workflow.run.assert_called_once_with(use_screener=True, top_n_stocks=7)

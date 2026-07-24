"""CLI entry-point flag plumbing for the daily tracker."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.parametrize(
    ("argv", "include_profile", "use_screener", "top_n"),
    [
        (["market-helm"], True, True, None),
        (["market-helm", "--quote-only"], False, True, None),
        (["market-helm", "--no-screener"], True, False, None),
        (["market-helm", "--top-n", "25"], True, True, 25),
        (
            ["market-helm", "--quote-only", "--no-screener", "--top-n", "10"],
            False,
            False,
            10,
        ),
    ],
)
def test_main_forwards_flags_to_workflow(argv, include_profile, use_screener, top_n, monkeypatch):
    monkeypatch.setattr("sys.argv", argv)
    workflow = MagicMock()
    workflow.run.return_value = {"success": True, "analysis": {}, "metadata": {}}

    with patch("src.cli.commands.StockTrackerWorkflow", return_value=workflow) as ctor:
        with patch("src.cli.commands.display_results") as display:
            from src.cli.commands import main

            main()

    ctor.assert_called_once_with(include_profile=include_profile)
    workflow.run.assert_called_once_with(use_screener=use_screener, top_n_stocks=top_n)
    display.assert_called_once_with(workflow.run.return_value)

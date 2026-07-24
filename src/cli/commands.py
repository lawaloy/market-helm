"""
MarketHelm CLI — command-line interface for the daily tracker workflow.
"""

from __future__ import annotations

from datetime import datetime
import math
import sys
from typing import Any

from ..workflows.tracker import StockTrackerWorkflow
from ..core.logger import setup_logger

# Set up logger
logger = setup_logger()

_MISSING = "—"


def _fmt_number(
    value: Any,
    precision: int = 2,
    *,
    signed: bool = False,
    default: str = _MISSING,
) -> str:
    """Format a numeric cell; None/NaN/Inf must not raise on :.Nf."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    if signed:
        return f"{number:+.{precision}f}"
    return f"{number:.{precision}f}"


def _fmt_pct(value: Any, precision: int = 2, *, signed: bool = False) -> str:
    formatted = _fmt_number(value, precision, signed=signed)
    return f"{formatted}%" if formatted != _MISSING else _MISSING


def _fmt_money(value: Any) -> str:
    formatted = _fmt_number(value, 2)
    return f"${formatted}" if formatted != _MISSING else _MISSING


def display_results(result: dict):
    """
    Display workflow results in CLI format.
    
    Args:
        result: Workflow result dictionary
    """
    if not result.get("success"):
        logger.error(f"Workflow failed: {result.get('error', 'Unknown error')}")
        return
    
    analysis = result.get("analysis", {})
    index_comparison = result.get("index_comparison", {})
    projections = result.get("projections", {})
    projection_summary = result.get("projection_summary", {})
    ai_summary = result.get("ai_summary")
    metadata = result.get("metadata", {})
    
    # Header
    logger.info("=" * 60)
    logger.info("Daily Market Summary")
    logger.info("=" * 60)
    
    # Display AI summary if available
    if ai_summary:
        logger.info("\n[AI Market Summary]")
        logger.info("-" * 60)
        logger.info(ai_summary)
        logger.info("-" * 60)
        logger.info("")
    
    # Summary statistics
    if "summary" in analysis:
        summary = analysis["summary"]
        logger.info(f"Date: {metadata.get('date', datetime.now().date())}")
        logger.info(f"Total Stocks Tracked: {summary.get('total_stocks', 0)}")
        logger.info(f"Gainers: {summary.get('gainers', 0)}")
        logger.info(f"Losers: {summary.get('losers', 0)}")
        logger.info(f"Unchanged: {summary.get('unchanged', 0)}")
        logger.info(
            f"Average Change: {_fmt_pct(summary.get('average_change_percent', 0))}"
        )
        logger.info("")
    
    # Top gainers
    if "top_gainers" in analysis and analysis["top_gainers"]:
        logger.info("Top 5 Gainers:")
        for i, stock in enumerate(analysis["top_gainers"], 1):
            logger.info(
                f"  {i}. {stock['symbol']} ({stock.get('name', 'N/A')}): "
                f"{_fmt_pct(stock.get('change_percent'), signed=True)} @ "
                f"{_fmt_money(stock.get('close'))}"
            )
        logger.info("")
    
    # Top losers
    if "top_losers" in analysis and analysis["top_losers"]:
        logger.info("Top 5 Losers:")
        for i, stock in enumerate(analysis["top_losers"], 1):
            logger.info(
                f"  {i}. {stock['symbol']} ({stock.get('name', 'N/A')}): "
                f"{_fmt_pct(stock.get('change_percent'))} @ "
                f"{_fmt_money(stock.get('close'))}"
            )
        logger.info("")
    
    # Index comparison
    if index_comparison:
        logger.info("Index Performance:")
        for index_name, stats in index_comparison.items():
            logger.info(f"  {index_name}:")
            logger.info(f"    Stocks: {stats['stock_count']}")
            logger.info(
                f"    Avg Change: {_fmt_pct(stats.get('average_change_percent'))}"
            )
            logger.info(f"    Gainers: {stats['gainers']} | Losers: {stats['losers']}")
        logger.info("")
    
    # Projection summary
    if projection_summary:
        logger.info("=" * 60)
        logger.info("STOCK PROJECTIONS - Next 5 Days")
        logger.info("=" * 60)
        
        # Overall projection stats
        logger.info(f"Total Projections: {projection_summary.get('total_projections', 0)}")
        logger.info(
            f"Average Confidence: "
            f"{_fmt_pct(projection_summary.get('average_confidence', 0), precision=1)}"
        )
        logger.info(
            f"Expected Market Move: "
            f"{_fmt_pct(projection_summary.get('average_expected_change', 0), signed=True)}"
        )
        logger.info("")
        
        # Recommendation breakdown
        recommendations = projection_summary.get('recommendations', {})
        if recommendations:
            logger.info("Recommendation Breakdown:")
            for rec, count in sorted(recommendations.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {rec}: {count}")
            logger.info("")
        
        # Top opportunities
        opportunities = projection_summary.get('top_opportunities', {})
        
        if opportunities.get('strong_buys'):
            logger.info("Top 5 BUY Opportunities:")
            for i, stock in enumerate(opportunities['strong_buys'][:5], 1):
                proj = projections.get(stock['symbol'])
                if proj:
                    logger.info(
                        f"  {i}. {proj['symbol']} - Target: "
                        f"{_fmt_money(proj.get('target_mid'))} "
                        f"({_fmt_pct(proj.get('expected_change_percent'), precision=1, signed=True)}) | "
                        f"Confidence: {proj.get('confidence', _MISSING)}%"
                    )
                    logger.info(f"     Reason: {proj.get('reason', '')}")
            logger.info("")
        
        if opportunities.get('strong_sells'):
            logger.info("Top 5 SELL Warnings:")
            for i, stock in enumerate(opportunities['strong_sells'][:5], 1):
                proj = projections.get(stock['symbol'])
                if proj:
                    logger.info(
                        f"  {i}. {proj['symbol']} - Target: "
                        f"{_fmt_money(proj.get('target_mid'))} "
                        f"({_fmt_pct(proj.get('expected_change_percent'), precision=1, signed=True)}) | "
                        f"Confidence: {proj.get('confidence', _MISSING)}%"
                    )
                    logger.info(f"     Reason: {proj.get('reason', '')}")
            logger.info("")
        
        logger.info(f"Full projections available in summary file")
        logger.info("=" * 60)
        logger.info("")
    
    # File paths
    file_paths = result.get("file_paths", {})
    if file_paths.get("data"):
        logger.info(f"Data saved to: {file_paths['data']}")
    if file_paths.get("summary"):
        logger.info(f"Summary saved to: {file_paths['summary']}")
    
    logger.info("=" * 60)
    logger.info("Daily tracking complete!")
    logger.info("=" * 60)


def main():
    """CLI entry point for MarketHelm (see also console script `market-helm`)."""
    import argparse

    if len(sys.argv) > 1 and sys.argv[1] == "alerts":
        from .alerts_commands import main as alerts_main

        alerts_main(sys.argv[2:])
        return

    parser = argparse.ArgumentParser(description='MarketHelm — daily market run (day-trading oriented)')
    parser.add_argument('--top-n', type=int, default=None, 
                       help='Limit to top N stocks by volume (e.g. --top-n 50 for day trading)')
    parser.add_argument('--no-screener', action='store_true',
                       help='Disable stock screener')
    parser.add_argument('--quote-only', action='store_true',
                       help='Fetch quotes only (skip company profile for faster refresh)')
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("MarketHelm - Daily Data Collection")
    if args.top_n:
        logger.info(f"Day Trading Mode: Top {args.top_n} stocks by volume")
    logger.info("=" * 60)
    logger.debug("Starting CLI interface")
    
    try:
        # Create and run workflow
        workflow = StockTrackerWorkflow(include_profile=not args.quote_only)
        result = workflow.run(use_screener=not args.no_screener, top_n_stocks=args.top_n)
        
        # Display results
        display_results(result)
        
        logger.debug("CLI completed successfully")
        
    except KeyboardInterrupt:
        logger.warning("Interrupted by user. Exiting.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()


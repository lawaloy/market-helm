# Stock Projections Feature

## Overview

The Stock Projection system analyzes current market data and generates intelligent 5-day price projections with buy/sell/hold recommendations for all tracked stocks.

## Features

### 1. **Price Projections**

- **5-Day Price Targets**: Low, Mid, and High price targets
- **Expected Change**: Percentage gain/loss projection
- **Projection Date**: Target date for the projection

### 2. **Recommendations**

- **STRONG BUY**: High momentum bullish stocks with strong confidence
- **BUY**: Moderate bullish momentum
- **HOLD**: Neutral or unclear direction
- **SELL**: Moderate bearish pressure
- **STRONG SELL**: Strong bearish momentum, potential decline

### 3. **Confidence Scoring**

- **0-100% Confidence Score**: Based on multiple factors:
  - Momentum strength
  - Volatility levels
  - Trading volume
  - Market capitalization
  - Price stability

### 4. **Risk Assessment**

- **Low Risk**: Stable, low volatility stocks
- **Medium Risk**: Moderate volatility
- **High Risk**: High volatility, unpredictable

### 5. **Trend Classification**

- **Bullish**: Upward momentum expected
- **Bearish**: Downward pressure expected
- **Neutral**: Sideways movement expected

## How It Works

### Technical Analysis Components

1. **Momentum Score** (-100 to +100)
   - Calculated from recent price changes
   - Positive = Bullish, Negative = Bearish
   - Magnitude = Strength of trend

2. **Volatility Score** (0 to 100)
   - Measures price stability
   - Lower = More predictable
   - Higher = More risk/uncertainty

3. **Price Target Calculation**
   - Based on momentum direction
   - Adjusted for volatility range
   - Considers mean reversion for extreme moves

4. **Confidence Calculation**
   - Higher momentum = Higher confidence
   - Lower volatility = Higher confidence
   - High volume = Higher confidence
   - Large market cap = Higher confidence

### Recommendation Logic

```text
STRONG BUY:  Momentum > 40 AND Volatility < 60
BUY:         Momentum > 15
HOLD:        Momentum between -15 and +15
SELL:        Momentum < -15
STRONG SELL: Momentum < -40 AND Volatility < 60
```

## Output Format

### Console Display

When you run the tracker, you'll see:

```text
=================================================================
STOCK PROJECTIONS - Next 5 Days
=================================================================
Total Projections: 178
Average Confidence: 73.2%
Expected Market Move: +0.13%

Recommendation Breakdown:
  HOLD: 93
  BUY: 34
  SELL: 31
  STRONG BUY: 13
  STRONG SELL: 7

Top 5 BUY Opportunities:
  1. AMAT - Target: $275.08 (+2.3%) | Confidence: 90%
     Reason: Positive +4.6% momentum; strong momentum

  ...

Top 5 SELL Warnings:
  1. ADBE - Target: $325.35 (-2.4%) | Confidence: 90%
     Reason: Negative -4.8% pressure; strong momentum

  ...
```

### Saved Files

#### 1. **Summary JSON** (`data/summary_YYYY-MM-DD.json`)

Includes complete projection data:

```json
{
  "projections": {
    "AAPL": {
      "symbol": "AAPL",
      "current_price": 150.50,
      "target_low": 148.20,
      "target_mid": 152.30,
      "target_high": 156.40,
      "expected_change_percent": 1.20,
      "recommendation": "BUY",
      "confidence": 75,
      "trend": "Bullish",
      "momentum_score": 25.5,
      "volatility_score": 35.2,
      "risk_level": "Low",
      "reason": "Positive +2.5% momentum; moderate momentum; high volume support",
      "projection_date": "2026-01-09",
      "generated_at": "2026-01-04T10:30:00"
    }
  },
  "projection_summary": {
    "total_projections": 178,
    "recommendations": {
      "STRONG BUY": 13,
      "BUY": 34,
      "HOLD": 93,
      "SELL": 31,
      "STRONG SELL": 7
    },
    "average_confidence": 73.2,
    "average_expected_change": 0.13
  }
}
```

#### 2. **Projections CSV** (`data/projections_YYYY-MM-DD.csv`)

Spreadsheet format for easy analysis:

```csv
symbol,current_price,target_low,target_mid,target_high,expected_change_percent,recommendation,confidence,trend,momentum_score,volatility_score,risk_level,reason,projection_date,generated_at
AAPL,150.50,148.20,152.30,156.40,1.20,BUY,75,Bullish,25.5,35.2,Low,"Positive +2.5% momentum; moderate momentum",2026-01-09,2026-01-04T10:30:00
```

## Usage

### Running the Tracker

The projection system is automatically integrated into the daily tracker:

```bash
# Run as normal - projections are included
python main.py

# Or via console script
market-helm
```

### Programmatic Access

```python
from src.workflows.tracker import StockTrackerWorkflow

# Run workflow
workflow = StockTrackerWorkflow()
result = workflow.run(use_screener=True)

if result['success']:
    # Access projections
    projections = result['projections']
    projection_summary = result['projection_summary']
    
    # Get specific stock projection
    aapl_projection = projections.get('AAPL')
    if aapl_projection:
        print(f"AAPL Target: ${aapl_projection['target_mid']:.2f}")
        print(f"Recommendation: {aapl_projection['recommendation']}")
        print(f"Confidence: {aapl_projection['confidence']}%")
```

### Custom Analysis

```python
from src.analysis.projector import StockProjector

# Initialize projector
projector = StockProjector()

# Generate projections for your data
current_stocks = [
    {'symbol': 'AAPL', 'close': 150.50, 'change_percent': 2.5, ...},
    # ... more stocks
]

projections = projector.generate_projections(current_stocks)
summary = projector.generate_projection_summary(projections)
```

## Important Notes

### ⚠️ Disclaimer

**Stock projections are for informational purposes only and should not be considered financial advice.**

- Projections are based on technical analysis of recent price action
- Past performance does not guarantee future results
- Markets are influenced by many unpredictable factors
- Always do your own research and consult with financial advisors
- Consider multiple sources before making investment decisions

### Limitations

1. **Short-term focus**: 5-day projections only
2. **Technical only**: No fundamental analysis (earnings, news, etc.)
3. **Historical data**: Requires at least 1 day of data
4. **No guarantees**: Market conditions can change rapidly

### Best Practices

✅ **Use as one input among many**
✅ **Compare with other analysis tools**
✅ **Monitor confidence scores**
✅ **Consider risk levels**
✅ **Track accuracy over time**
✅ **Adjust for market conditions**

## Projection accuracy (shipped)

The dashboard and backend compare past **`target_mid`** values to the first available **closing price** on or after the projection target date. Summary API: **`GET /api/history/accuracy`** (see [PROJECT_STATUS.md](PROJECT_STATUS.md)). This complements the projector: scoring lives in the dashboard data layer, not inside `StockProjector`.

## Future Enhancements

Potential improvements for future versions:

- [ ] Multi-timeframe projections (1-day, 5-day, 30-day)
- [ ] Richer accuracy analytics (e.g. by confidence band, business-calendar targets — see [PROJECT_STATUS.md](PROJECT_STATUS.md))
- [ ] Machine learning model integration
- [ ] Fundamental analysis factors
- [ ] News sentiment integration
- [ ] Sector correlation analysis
- [ ] Backtesting framework
- [ ] More alert channels and rules for high-confidence opportunities (partial alerting exists; see [ALERTING_DESIGN.md](ALERTING_DESIGN.md))

## Architecture

### Module Structure

```text
src/analysis/projector.py
├── StockProjector
│   ├── generate_projections()      # Main entry point
│   ├── _project_stock()            # Single stock projection
│   ├── _calculate_momentum()       # Momentum scoring
│   ├── _calculate_volatility()     # Volatility analysis
│   ├── _determine_trend()          # Trend classification
│   ├── _calculate_targets()        # Price target calculation
│   ├── _generate_recommendation()  # Buy/sell logic
│   ├── _calculate_confidence()     # Confidence scoring
│   └── generate_projection_summary() # Aggregate statistics
```

### Integration Points

- **Workflow**: `src/workflows/tracker.py` - Step 4: Generate projections
- **CLI**: `src/cli/commands.py` - Display projection results
- **Storage**: `src/storage/data_storage.py` - Save projections to CSV/JSON

## Example Results

Based on actual test with 197 stocks:

- **Total Projections**: 178 (90% success rate)
- **Average Confidence**: 73.2%
- **Expected Market Move**: +0.13%

### Top Performers (Test Data)

**Top BUY Opportunities:**

1. AMAT: $268.87 → $275.08 (+2.3%, 90% confidence)
2. BA: $227.77 → $233.36 (+2.5%, 90% confidence)
3. AMD: $223.47 → $228.33 (+2.2%, 90% confidence)

**Top SELL Warnings:**

1. ADBE: $333.30 → $325.35 (-2.4%, 90% confidence)
2. PLTR: $167.86 → $165.53 (-1.4%, 90% confidence)
3. INTU: $629.46 → $613.80 (-2.5%, 90% confidence)

## Testing

The projection system has been tested with real market data and produces consistent, reasonable projections based on technical analysis principles.

### Test Results

- ✅ Successfully generates projections for 90%+ of stocks
- ✅ Confidence scores properly weighted
- ✅ Recommendations align with momentum/trend
- ✅ Price targets within reasonable ranges
- ✅ Risk levels correctly assessed

## Support

For questions or issues with the projection system:

1. Check projection confidence scores - low confidence = less reliable
2. Review the `reason` field for explanation of projection
3. Compare multiple days of projections for trends
4. Monitor actual vs. projected performance

---

**Doc scope:** Describes the core **`StockProjector`** pipeline. For shipping status and related APIs, see [PROJECT_STATUS.md](PROJECT_STATUS.md) and the main [README.md](../README.md).

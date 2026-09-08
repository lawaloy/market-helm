# Projection evaluator baseline v1

This package preserves a deterministic scenario baseline for MarketHelm's
five-session XNYS projection evaluator. It covers:

- premarket, intraday, and post-close horizon anchors across a market holiday;
- every confidence cohort, including missing confidence;
- correct, incorrect, and flat directional outcomes;
- target-band hits, misses, and unavailable bands;
- missing actual closes, pending projections, and invalid rows; and
- newest-first sample ordering.

The CSVs are synthetic and exist to detect evaluator/reporting regressions. The
resulting metrics are **not model-performance evidence** and must not be used to
calibrate confidence. Real calibration requires separately preserved,
out-of-sample production projections and exact target-session closes.

Verify the committed report:

```bash
python3 scripts/projection_baseline.py check
```

After an intentional evaluator contract change, review the semantic impact and
regenerate the report explicitly:

```bash
python3 scripts/projection_baseline.py update
python3 scripts/projection_baseline.py check
```

The check is also exercised by the Python test suite.

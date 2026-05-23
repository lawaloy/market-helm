param(
    [int]$IntervalSeconds = 0
)

# Long-running alert worker: evaluates watches on a schedule (default every 5 minutes).
# Requires FINNHUB_API_KEY only when watches need live quotes for symbols missing from saved data.
#
# Interval: pass -IntervalSeconds, or set ALERT_CHECK_INTERVAL_SECONDS in the environment.
# One-shot (cron / Task Scheduler): python -m src.cli.commands alerts run
#
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
    if ($IntervalSeconds -gt 0) {
        python -m src.cli.commands alerts run --loop --interval $IntervalSeconds
    } else {
        python -m src.cli.commands alerts run --loop
    }
} finally {
    Pop-Location
}

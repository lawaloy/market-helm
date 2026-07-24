"""
Refresh API endpoints — trigger the daily MarketHelm run to fetch new data.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
import threading
import time
import logging

from dashboard.backend.auth import require_user_id

logger = logging.getLogger(__name__)

router = APIRouter()

# Track refresh status
refresh_status = {
    "is_running": False,
    "last_refresh": None,
    "last_status": "idle",
    "progress": "Idle."
}

_refresh_process: subprocess.Popen | None = None
_refresh_cancel_event = threading.Event()


def _has_refresh_credentials(project_root: Path) -> bool:
    """True when Finnhub can be configured via env var or a project .env file."""
    return bool(os.getenv("FINNHUB_API_KEY")) or (project_root / ".env").exists()


class RefreshResponse(BaseModel):
    status: str
    message: str
    last_refresh: str | None
    is_running: bool


class RefreshStatusResponse(BaseModel):
    is_running: bool
    last_refresh: str | None
    last_status: str | None
    progress: str | None


def run_daily_tracker():
    """Run the MarketHelm CLI (`market-helm`) in a separate process."""
    global _refresh_process
    try:
        refresh_status["is_running"] = True
        refresh_status["progress"] = "Starting market-helm..."
        refresh_status["last_status"] = "running"
        _refresh_cancel_event.clear()
        
        # Repo checkout: run top-level main.py. Pip install: run same CLI as console_scripts.
        project_root = Path(__file__).parent.parent.parent.parent
        main_script = project_root / "main.py"
        if main_script.is_file():
            command = [sys.executable, str(main_script)]
        else:
            command = [sys.executable, "-m", "src.cli.commands"]

        # Run market-helm (default to top 10 for faster refresh, minimum 10)
        top_n_value = os.getenv("REFRESH_TOP_N", "10")
        try:
            top_n = max(0, int(top_n_value))
        except ValueError:
            top_n = 10
        if top_n > 0:
            top_n = max(10, top_n)  # At least 10 stocks when using limit
        if top_n:
            command.extend(["--top-n", str(top_n)])


        no_screener = os.getenv("REFRESH_NO_SCREENER", "1").lower() in {"1", "true", "yes"}
        if no_screener:
            command.append("--no-screener")

        refresh_status["progress"] = "Refreshing..."

        env = os.environ.copy()
        env["STOCK_FETCH_MAX_WORKERS"] = os.getenv("REFRESH_MAX_WORKERS", "4")

        # Parse timeout before spawn so a bad env var cannot orphan a running child
        # (ValueError used to trip the outer except after Popen and clear _refresh_process).
        timeout_raw = os.getenv("REFRESH_TIMEOUT_SECONDS", "600")
        try:
            max_seconds = max(1, int(timeout_raw))
        except (TypeError, ValueError):
            max_seconds = 600

        # Do not use PIPE for stdout/stderr: the tracker logs heavily to the console.
        # Unread PIPE buffers deadlock the child once full (parent only drains in communicate()).
        _refresh_process = subprocess.Popen(
            command,
            cwd=str(project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )

        start_time = time.time()

        while True:
            if _refresh_cancel_event.is_set():
                refresh_status["last_status"] = "cancelled"
                refresh_status["progress"] = "Refresh cancelled."
                if _refresh_process.poll() is None:
                    _refresh_process.terminate()
                break

            if _refresh_process.poll() is not None:
                break

            elapsed = int(time.time() - start_time)

            refresh_status["progress"] = f"Refreshing..."

            if elapsed >= max_seconds:
                refresh_status["last_status"] = "timeout"
                refresh_status["progress"] = "Refresh timed out. Please try again."
                _refresh_process.terminate()
                break

            time.sleep(2)

        try:
            _refresh_process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            _refresh_process.kill()
            _refresh_process.wait(timeout=10)

        if _refresh_cancel_event.is_set():
            refresh_status["last_status"] = "cancelled"
            refresh_status["progress"] = "Refresh cancelled."
            return

        if refresh_status["last_status"] == "timeout":
            return

        if _refresh_process.returncode == 0:
            refresh_status["last_status"] = "success"
            refresh_status["last_refresh"] = datetime.now().isoformat()
            refresh_status["progress"] = "Data refresh completed successfully!"
            try:
                from src.alerts.alert_worker import run_check_once

                result = run_check_once()
                if result.get("triggered", 0) > 0:
                    logger.info("Alerts triggered after refresh: %s", result["triggered"])
            except Exception as exc:
                logger.warning("Post-refresh alert check failed: %s", exc)
        else:
            refresh_status["last_status"] = "error"
            refresh_status["progress"] = "Refresh failed. Please try again."
    except Exception:
        refresh_status["last_status"] = "error"
        refresh_status["progress"] = "Refresh failed. Please try again."
    finally:
        _refresh_process = None
        refresh_status["is_running"] = False


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    dependencies=[Depends(require_user_id)],
)
async def trigger_refresh(background_tasks: BackgroundTasks):
    """
    Trigger a data refresh (daily run) to fetch fresh data.

    This will:
    1. Run the tracker (`main.py` or `python -m src.cli.commands`)
    2. Fetch latest data from Finnhub API
    3. Generate new projections
    4. Save updated CSV/JSON files
    5. Dashboard will automatically show new data
    """
    if refresh_status["is_running"]:
        return RefreshResponse(
            status="already_running",
            message="Data refresh is already in progress. Please wait.",
            last_refresh=refresh_status.get("last_refresh"),
            is_running=True
        )

    project_root = Path(__file__).parent.parent.parent.parent
    if not _has_refresh_credentials(project_root):
        refresh_status["last_status"] = "error"
        refresh_status["progress"] = "Refresh failed. Please check your API key configuration."
        return RefreshResponse(
            status="error",
            message="Refresh failed. Please check your API key configuration.",
            last_refresh=refresh_status.get("last_refresh"),
            is_running=False
        )

    refresh_status["last_status"] = "running"
    refresh_status["progress"] = "Starting market-helm..."
    refresh_status["is_running"] = True

    # Start refresh in background
    thread = threading.Thread(target=run_daily_tracker, daemon=True)
    thread.start()
    
    return RefreshResponse(
        status="started",
        message="Latest data will load when ready.",
        last_refresh=refresh_status.get("last_refresh"),
        is_running=True
    )


@router.get("/refresh/status", response_model=RefreshStatusResponse)
async def get_refresh_status():
    """Get the current status of data refresh"""
    if not refresh_status.get("is_running") and not refresh_status.get("last_status"):
        refresh_status["last_status"] = "idle"
        refresh_status["progress"] = "Idle."
    return RefreshStatusResponse(
        is_running=refresh_status["is_running"],
        last_refresh=refresh_status.get("last_refresh"),
        last_status=refresh_status.get("last_status"),
        progress=refresh_status.get("progress")
    )


@router.post(
    "/refresh/cancel",
    response_model=RefreshStatusResponse,
    dependencies=[Depends(require_user_id)],
)
async def cancel_refresh():
    """Cancel the current refresh job if running."""
    if not refresh_status["is_running"]:
        raise HTTPException(status_code=400, detail="No refresh in progress.")

    refresh_status["progress"] = "Cancelling refresh..."
    refresh_status["last_status"] = "cancelled"
    _refresh_cancel_event.set()

    if _refresh_process and _refresh_process.poll() is None:
        _refresh_process.terminate()
        try:
            _refresh_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _refresh_process.kill()

    refresh_status["is_running"] = False

    return RefreshStatusResponse(
        is_running=refresh_status["is_running"],
        last_refresh=refresh_status.get("last_refresh"),
        last_status=refresh_status.get("last_status"),
        progress=refresh_status.get("progress")
    )

"""
Refresh API endpoints - Trigger stock tracker to fetch new data
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
import threading
import time

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


def run_stock_tracker():
    """Run the stock tracker in a separate process"""
    global _refresh_process
    try:
        refresh_status["is_running"] = True
        refresh_status["progress"] = "Starting stock tracker..."
        refresh_status["last_status"] = "running"
        _refresh_cancel_event.clear()
        
        # Repo checkout: run top-level main.py. Pip install: run same CLI as console_scripts.
        project_root = Path(__file__).parent.parent.parent.parent
        main_script = project_root / "main.py"
        if main_script.is_file():
            command = [sys.executable, str(main_script)]
        else:
            command = [sys.executable, "-m", "src.cli.commands"]

        # Run the stock tracker (default to top 10 for faster refresh, minimum 10)
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

        _refresh_process = subprocess.Popen(
            command,
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )

        max_seconds = int(os.getenv("REFRESH_TIMEOUT_SECONDS", "600"))
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
            stdout, stderr = _refresh_process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            _refresh_process.kill()
            stdout, stderr = _refresh_process.communicate()

        if _refresh_cancel_event.is_set():
            refresh_status["last_status"] = "cancelled"
            refresh_status["progress"] = "Refresh cancelled."
            return

        if _refresh_process.returncode == 0:
            refresh_status["last_status"] = "success"
            refresh_status["last_refresh"] = datetime.now().isoformat()
            refresh_status["progress"] = "Data refresh completed successfully!"
        else:
            refresh_status["last_status"] = "error"
            refresh_status["progress"] = "Refresh failed. Please try again."
    except Exception:
        refresh_status["last_status"] = "error"
        refresh_status["progress"] = "Refresh failed. Please try again."
    finally:
        _refresh_process = None
        refresh_status["is_running"] = False


@router.post("/refresh", response_model=RefreshResponse)
async def trigger_refresh(background_tasks: BackgroundTasks):
    """
    Trigger the stock tracker to fetch fresh data
    
    This will:
    1. Run the stock tracker (main.py)
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
    has_env_key = bool(os.getenv("FINNHUB_API_KEY"))
    has_env_file = (project_root / ".env").exists()
    if not (has_env_key or has_env_file):
        refresh_status["last_status"] = "error"
        refresh_status["progress"] = "Refresh failed. Please check your API key configuration."
        return RefreshResponse(
            status="error",
            message="Refresh failed. Please check your API key configuration.",
            last_refresh=refresh_status.get("last_refresh"),
            is_running=False
        )

    refresh_status["last_status"] = "running"
    refresh_status["progress"] = "Starting stock tracker..."
    
    # Start refresh in background
    thread = threading.Thread(target=run_stock_tracker, daemon=True)
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


@router.post("/refresh/cancel", response_model=RefreshStatusResponse)
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

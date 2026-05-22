"""
FastAPI backend for the MarketHelm dashboard.
"""
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
import sys
import os

# Add repo root to path when running from source (development) so src/ is importable.
_here = Path(__file__).resolve()
for _p in _here.parents:
    if (_p / "main.py").is_file() and (_p / "src").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

# Load .env from cwd, then repo root (dev), then user config dir (pip install)
try:
    from dotenv import load_dotenv
    load_dotenv()
    for _p in _here.parents:
        if (_p / "main.py").is_file() and (_p / ".env").is_file():
            load_dotenv(_p / ".env")
            break
    _user_env = Path.home() / ".market-helm" / ".env"
    if _user_env.is_file():
        load_dotenv(_user_env, override=True)
except ImportError:
    pass

from contextlib import asynccontextmanager
import threading

from dashboard.backend.api import market, projections, stocks, refresh, history, alerts
from dashboard.backend.api.market import get_market_summary


def _startup_alert_check() -> None:
    try:
        from src.alerts.alert_runner import evaluate_alerts_from_latest_data

        result = evaluate_alerts_from_latest_data()
        triggered = result.get("triggered", 0)
        if triggered:
            logging.getLogger(__name__).info("Startup alert check triggered %s watch(es)", triggered)
    except Exception as exc:
        logging.getLogger(__name__).warning("Startup alert check failed: %s", exc)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    threading.Thread(target=_startup_alert_check, daemon=True).start()
    yield


app = FastAPI(
    title="MarketHelm API",
    description="API for stock market data, projections, and recommendations",
    version="0.2.16",
    lifespan=lifespan,
)

# CORS configuration for local development
default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:3003",
    "http://localhost:3004",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
cors_env = os.getenv("CORS_ORIGINS", "")
env_origins = [origin.strip() for origin in cors_env.split(",") if origin.strip()]
origins = env_origins or default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(market.router, prefix="/api/market", tags=["Market"])
app.include_router(projections.router, prefix="/api/projections", tags=["Projections"])
app.include_router(stocks.router, prefix="/api/stocks", tags=["Stocks"])
app.include_router(refresh.router, prefix="/api", tags=["Refresh"])
app.include_router(history.router, prefix="/api/history", tags=["History"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/data-info")
async def data_info():
    """Data status: path, latest date, and whether we need to fetch for the most recent trading day."""
    from dashboard.backend.services.data_loader import get_data_loader, get_most_recent_trading_day
    try:
        loader = get_data_loader()
    except ValueError:
        raise HTTPException(status_code=404, detail="No data available.")
    target_trading_day = get_most_recent_trading_day()
    return {
        "data_dir": str(loader.data_dir),
        "latest_date": loader.get_latest_date(),
        "target_trading_day": target_trading_day,
        "needs_fetch": loader.needs_fetch_for_latest_trading_day(),
        "available_dates": loader.get_available_dates()[:5],
    }


@app.get("/api/summary")
async def api_summary():
    """Market summary (AI or demo)."""
    return await get_market_summary()


_STATIC_DIR = Path(__file__).resolve().parent / "static"
_INDEX = _STATIC_DIR / "index.html"


def _safe_static_file(full_path: str) -> Path | None:
    """Return a file under the SPA static root, or None if the path is invalid."""
    normalized = os.path.normpath(full_path.replace("\\", "/")).lstrip("/")
    if not normalized or normalized.startswith("..") or os.path.isabs(normalized):
        return None
    base = os.path.realpath(_STATIC_DIR)
    candidate = os.path.realpath(os.path.join(base, normalized))
    if os.path.commonpath([base, candidate]) != base:
        return None
    path = Path(candidate)
    return path if path.is_file() else None


if _STATIC_DIR.is_dir() and _INDEX.is_file():

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_or_static(full_path: str):
        """
        Serve Vite-built assets; unknown paths return index.html so React Router
        deep links (e.g. /summary) work when the SPA is served from FastAPI.
        """
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        static_file = _safe_static_file(full_path)
        if static_file is not None:
            return FileResponse(static_file)
        return FileResponse(_INDEX)
else:

    @app.get("/")
    async def root():
        """Health check when SPA bundle is not present (e.g. dev without frontend build)."""
        return {
            "status": "healthy",
            "service": "MarketHelm API",
            "version": "0.2.16",
            "spa": False,
        }


if __name__ == "__main__":
    import uvicorn
    reload = os.getenv("UVICORN_RELOAD", "").lower() in {"1", "true", "yes"}
    uvicorn.run("dashboard.backend.main:app", host="0.0.0.0", port=8000, reload=reload)

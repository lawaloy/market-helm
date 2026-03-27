"""Console entry: `stock-tracker-dashboard` — serves API + bundled SPA."""

import os


def main() -> None:
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "dashboard.backend.main:app",
        host=host,
        port=port,
        reload=os.getenv("UVICORN_RELOAD", "").lower() in {"1", "true", "yes"},
    )

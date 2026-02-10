"""FastAPI entry point for Local Sidekick Cloud Run API."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api import reports, settings, statistics
from server.auth import router as auth_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Local Sidekick API",
    version="0.1.0",
    description="Cloud Run backend for the Local Sidekick productivity assistant.",
)

# CORS - allow all origins during development (Electron app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(statistics.router, prefix="/api/statistics", tags=["statistics"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health():
    """Simple liveness / readiness probe."""
    return {"status": "ok", "service": "local-sidekick-api"}

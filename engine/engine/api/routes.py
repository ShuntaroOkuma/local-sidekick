"""REST API routes for the Local Sidekick Engine.

Endpoints:
    GET  /api/health          -> Health check
    GET  /api/state           -> Current integrated state
    GET  /api/history         -> State history (with time range query)
    GET  /api/daily-stats     -> Today's daily statistics
    GET  /api/settings        -> Current engine settings
    PUT  /api/settings        -> Update engine settings
    POST /api/engine/start    -> Start monitoring
    POST /api/engine/stop     -> Stop monitoring
    POST /api/engine/pause    -> Pause monitoring (system sleep)
    POST /api/engine/resume   -> Resume monitoring (system wake)
    GET  /api/reports          -> List available report dates
    GET  /api/reports/{date}   -> Get a specific past report
    POST /api/cloud/login     -> Login to Cloud Run
    POST /api/cloud/register  -> Register on Cloud Run
    POST /api/cloud/logout    -> Clear cloud auth
"""

from __future__ import annotations

import datetime
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from engine.api.cloud_client import (
    cloud_generate_report,
    cloud_get_report,
    cloud_health_check,
    cloud_list_reports,
    cloud_login,
    cloud_register,
)
from engine.config import EngineConfig, load_config, save_config
from engine.history.aggregator import build_bucketed_segments, compute_daily_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# --- Request/Response models ---


class HealthResponse(BaseModel):
    status: str = "ok"
    monitoring: bool = False
    uptime_seconds: float = 0.0


class StateResponse(BaseModel):
    state: str
    confidence: float
    camera_state: Optional[str] = None
    pc_state: Optional[str] = None
    reasoning: str = ""
    source: str = ""
    timestamp: float = 0.0


class SettingsResponse(BaseModel):
    camera_enabled: bool
    camera_index: int
    model_tier: str
    sync_enabled: bool
    avatar_enabled: bool
    drowsy_cooldown_minutes: int
    distracted_cooldown_minutes: int
    over_focus_cooldown_minutes: int
    drowsy_trigger_buckets: int
    distracted_trigger_buckets: int
    over_focus_window_buckets: int
    over_focus_threshold_buckets: int
    cloud_run_url: str = ""
    cloud_auth_email: str = ""


class SettingsUpdate(BaseModel):
    camera_enabled: Optional[bool] = None
    camera_index: Optional[int] = None
    model_tier: Optional[str] = None
    sync_enabled: Optional[bool] = None
    avatar_enabled: Optional[bool] = None
    drowsy_cooldown_minutes: Optional[int] = None
    distracted_cooldown_minutes: Optional[int] = None
    over_focus_cooldown_minutes: Optional[int] = None
    drowsy_trigger_buckets: Optional[int] = None
    distracted_trigger_buckets: Optional[int] = None
    over_focus_window_buckets: Optional[int] = None
    over_focus_threshold_buckets: Optional[int] = None
    cloud_run_url: Optional[str] = None


class EngineActionResponse(BaseModel):
    status: str
    message: str


# --- Shared state (set by main.py at startup) ---

_engine_state: dict = {
    "monitoring": False,
    "start_time": None,
    "current_state": None,
    "history_store": None,
    "start_callback": None,
    "stop_callback": None,
}


def set_engine_state(key: str, value: object) -> None:
    """Set a shared engine state value (called from main.py)."""
    _engine_state[key] = value


def get_engine_state(key: str) -> object:
    """Get a shared engine state value."""
    return _engine_state.get(key)


# --- Route handlers ---


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    monitoring = _engine_state.get("monitoring", False)
    start_time = _engine_state.get("start_time")
    uptime = time.time() - start_time if start_time else 0.0

    return HealthResponse(
        status="ok",
        monitoring=monitoring,
        uptime_seconds=round(uptime, 1),
    )


@router.get("/state", response_model=StateResponse)
async def get_state() -> StateResponse:
    """Get the current integrated state."""
    current = _engine_state.get("current_state")
    if current is None:
        return StateResponse(
            state="unknown",
            confidence=0.0,
            reasoning="Engine not running or no data yet",
        )

    return StateResponse(
        state=current.get("state", "unknown"),
        confidence=current.get("confidence", 0.0),
        camera_state=current.get("camera_state"),
        pc_state=current.get("pc_state"),
        reasoning=current.get("reasoning", ""),
        source=current.get("source", ""),
        timestamp=current.get("timestamp", 0.0),
    )


@router.get("/history")
async def get_history(
    start: Optional[float] = Query(None, description="Start timestamp (Unix epoch)"),
    end: Optional[float] = Query(None, description="End timestamp (Unix epoch)"),
    limit: int = Query(1000, ge=1, le=10000, description="Max entries to return"),
) -> dict:
    """Get state history within a time range."""
    store = _engine_state.get("history_store")
    if store is None:
        raise HTTPException(status_code=503, detail="History store not available")

    logs = await store.get_state_log(start_time=start, end_time=end, limit=limit)
    notifications = await store.get_notifications(start_time=start, end_time=end)

    return {
        "state_log": logs,
        "notifications": notifications,
        "count": len(logs),
    }


@router.get("/history/bucketed")
async def get_history_bucketed(
    start: float = Query(..., description="Start timestamp (Unix epoch)"),
    end: float = Query(..., description="End timestamp (Unix epoch)"),
    bucket_minutes: int = Query(5, ge=1, le=60, description="Bucket width in minutes"),
) -> dict:
    """Get bucketed state history segments for timeline display."""
    store = _engine_state.get("history_store")
    if store is None:
        raise HTTPException(status_code=503, detail="History store not available")

    logs = await store.get_state_log(start_time=start, end_time=end, limit=100000)
    segments = build_bucketed_segments(logs, bucket_minutes=bucket_minutes)
    return {"segments": segments, "count": len(segments)}


@router.get("/daily-stats")
async def get_daily_stats(
    date: Optional[str] = Query(None, description="Date (YYYY-MM-DD), defaults to today"),
) -> dict:
    """Get daily statistics, computing from state_log if needed."""
    store = _engine_state.get("history_store")
    if store is None:
        raise HTTPException(status_code=503, detail="History store not available")

    if date is None:
        date = datetime.date.today().isoformat()

    # Try to get cached summary first
    summary = await store.get_daily_summary(date)
    if summary is not None:
        return summary

    # Compute from state_log
    stats = await compute_daily_stats(store, date)
    return stats


@router.get("/settings", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """Get current engine settings."""
    config = load_config()
    return _config_to_response(config)


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(update: SettingsUpdate) -> SettingsResponse:
    """Update engine settings. Only provided fields are updated.

    Changes are saved to disk AND applied to the running engine
    via the global _config and notification engine refresh.
    """
    config = load_config()

    update_data = update.model_dump(exclude_none=True)
    for key, value in update_data.items():
        if hasattr(config, key):
            setattr(config, key, value)

    save_config(config)

    # Apply to running engine loops (they read from global _config)
    apply_callback = _engine_state.get("apply_config_callback")
    if apply_callback is not None:
        await apply_callback(config)

    return _config_to_response(config)


class CloudAuthRequest(BaseModel):
    email: str
    password: str


def _config_to_response(config: EngineConfig) -> SettingsResponse:
    """Convert an EngineConfig to a SettingsResponse."""
    return SettingsResponse(
        camera_enabled=config.camera_enabled,
        camera_index=config.camera_index,
        model_tier=config.model_tier,
        sync_enabled=config.sync_enabled,
        avatar_enabled=config.avatar_enabled,
        drowsy_cooldown_minutes=config.drowsy_cooldown_minutes,
        distracted_cooldown_minutes=config.distracted_cooldown_minutes,
        over_focus_cooldown_minutes=config.over_focus_cooldown_minutes,
        drowsy_trigger_buckets=config.drowsy_trigger_buckets,
        distracted_trigger_buckets=config.distracted_trigger_buckets,
        over_focus_window_buckets=config.over_focus_window_buckets,
        over_focus_threshold_buckets=config.over_focus_threshold_buckets,
        cloud_run_url=config.cloud_run_url,
        cloud_auth_email=config.cloud_auth_email,
    )


# --- Notification endpoints ---


@router.get("/notifications")
async def get_notifications(
    start: Optional[float] = Query(None),
    end: Optional[float] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> list:
    """Get notifications within a time range."""
    store = _engine_state.get("history_store")
    if store is None:
        raise HTTPException(status_code=503, detail="History store not available")
    return await store.get_notifications(start_time=start, end_time=end, limit=limit)


@router.get("/notifications/pending")
async def get_pending_notifications() -> list:
    """Get pending (unresponded) notifications."""
    store = _engine_state.get("history_store")
    if store is None:
        return []
    # Get recent notifications (last 5 minutes) without user_action
    start = time.time() - 300
    all_notifs = await store.get_notifications(start_time=start)
    return [n for n in all_notifs if not n.get("user_action")]


@router.post("/notifications/{notification_id}/respond")
async def respond_to_notification(
    notification_id: int,
    body: dict,
) -> dict:
    """Record user response to a notification."""
    store = _engine_state.get("history_store")
    if store is None:
        raise HTTPException(status_code=503, detail="History store not available")
    action = body.get("action", "dismissed")
    await store.update_notification_action(notification_id, action)
    return {"status": "ok", "action": action}


# --- Report list/get endpoints ---


@router.get("/reports")
async def list_reports() -> dict:
    """List available report dates. Returns empty list if sync is disabled."""
    config = load_config()
    if not (config.sync_enabled and config.cloud_run_url and config.cloud_auth_token):
        return {"dates": []}

    dates = await cloud_list_reports(config.cloud_run_url, config.cloud_auth_token)
    if dates is None:
        return {"dates": []}
    return {"dates": dates}


@router.get("/reports/{date}")
async def get_report(date: str) -> dict:
    """Get a specific past report. Returns 503 if sync is disabled."""
    config = load_config()
    if not (config.sync_enabled and config.cloud_run_url and config.cloud_auth_token):
        raise HTTPException(status_code=503, detail="Cloud sync is not enabled")

    report = await cloud_get_report(config.cloud_run_url, config.cloud_auth_token, date)
    if report is None:
        raise HTTPException(status_code=404, detail=f"No report found for date: {date}")
    return report


# --- Report proxy endpoint ---


@router.post("/reports/generate")
async def generate_report(
    date: Optional[str] = Query(None),
) -> dict:
    """Generate daily report. Proxies to Cloud Run if sync is enabled,
    otherwise computes a local summary."""
    store = _engine_state.get("history_store")
    if store is None:
        raise HTTPException(status_code=503, detail="History store not available")

    if date is None:
        date = datetime.date.today().isoformat()

    stats = await compute_daily_stats(store, date)

    config = load_config()
    if config.sync_enabled and config.cloud_run_url and config.cloud_auth_token:
        report = await cloud_generate_report(
            config.cloud_run_url, config.cloud_auth_token, stats,
        )
        if report is not None:
            stats["report"] = report
            stats["report_source"] = "cloud"
            return stats
        logger.warning("Cloud report failed, falling back to local")

    # Local fallback
    stats["report"] = {
        "summary": f"本日の作業統計: 集中 {stats.get('focused_minutes', 0):.0f}分",
        "highlights": [],
        "concerns": [],
        "tomorrow_tip": "明日も頑張りましょう！",
    }
    stats["report_source"] = "local"
    return stats


# --- Cloud URL check endpoint ---


class CloudUrlCheckRequest(BaseModel):
    url: str


@router.post("/cloud/check-url")
async def cloud_check_url(body: CloudUrlCheckRequest) -> dict:
    """Check if a Cloud Run URL is reachable."""
    ok = await cloud_health_check(body.url)
    if not ok:
        raise HTTPException(status_code=400, detail="Cloud Run URLに接続できません")
    return {"status": "ok"}


# --- Cloud auth endpoints ---


async def _cloud_auth(body: CloudAuthRequest, mode: str) -> dict:
    """Shared logic for cloud login/register."""
    config = load_config()
    if not config.cloud_run_url:
        raise HTTPException(status_code=400, detail="cloud_run_url not configured")

    fn = cloud_login if mode == "login" else cloud_register
    result = await fn(config.cloud_run_url, body.email, body.password)
    if result is None:
        detail = "Cloud login failed" if mode == "login" else "Cloud registration failed"
        status = 401 if mode == "login" else 400
        raise HTTPException(status_code=status, detail=detail)

    config.cloud_auth_token = result["access_token"]
    config.cloud_auth_email = body.email
    save_config(config)

    return {"status": "ok", "email": body.email}


@router.post("/cloud/login")
async def cloud_login_endpoint(body: CloudAuthRequest) -> dict:
    """Login to Cloud Run and save the JWT token to config."""
    return await _cloud_auth(body, "login")


@router.post("/cloud/register")
async def cloud_register_endpoint(body: CloudAuthRequest) -> dict:
    """Register on Cloud Run and save the JWT token to config."""
    return await _cloud_auth(body, "register")


@router.post("/cloud/logout")
async def cloud_logout_endpoint() -> dict:
    """Clear cloud auth info from config."""
    config = load_config()
    config.cloud_auth_token = ""
    config.cloud_auth_email = ""
    save_config(config)

    return {"status": "ok"}


@router.post("/engine/start", response_model=EngineActionResponse)
async def start_engine() -> EngineActionResponse:
    """Start the monitoring engine."""
    if _engine_state.get("monitoring"):
        return EngineActionResponse(status="ok", message="Already running")

    callback = _engine_state.get("start_callback")
    if callback is not None:
        await callback()

    return EngineActionResponse(status="ok", message="Monitoring started")


@router.post("/engine/stop", response_model=EngineActionResponse)
async def stop_engine() -> EngineActionResponse:
    """Stop the monitoring engine."""
    if not _engine_state.get("monitoring"):
        return EngineActionResponse(status="ok", message="Already stopped")

    callback = _engine_state.get("stop_callback")
    if callback is not None:
        await callback()

    return EngineActionResponse(status="ok", message="Monitoring stopped")


@router.post("/engine/pause", response_model=EngineActionResponse)
async def pause_engine() -> EngineActionResponse:
    """Pause monitoring (e.g. system sleep).

    Loops stay alive but skip work. No state is recorded to history.
    """
    if _engine_state.get("paused"):
        return EngineActionResponse(status="ok", message="Already paused")
    if not _engine_state.get("monitoring"):
        return EngineActionResponse(status="ok", message="Not monitoring")

    callback = _engine_state.get("pause_callback")
    if callback is not None:
        await callback()

    return EngineActionResponse(status="ok", message="Monitoring paused")


@router.post("/engine/resume", response_model=EngineActionResponse)
async def resume_engine() -> EngineActionResponse:
    """Resume monitoring after pause (e.g. system wake).

    Resets stale state and notification timers.
    """
    if not _engine_state.get("paused"):
        return EngineActionResponse(status="ok", message="Not paused")

    callback = _engine_state.get("resume_callback")
    if callback is not None:
        await callback()

    return EngineActionResponse(status="ok", message="Monitoring resumed")

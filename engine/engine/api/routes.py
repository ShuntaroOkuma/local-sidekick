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
"""

from __future__ import annotations

import datetime
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from engine.config import EngineConfig, load_config, save_config
from engine.history.aggregator import compute_daily_stats

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
    timestamp: float = 0.0


class SettingsResponse(BaseModel):
    working_hours_start: str
    working_hours_end: str
    max_notifications_per_day: int
    camera_enabled: bool
    camera_index: int
    model_tier: str
    sync_enabled: bool
    drowsy_cooldown_minutes: int
    distracted_cooldown_minutes: int
    over_focus_cooldown_minutes: int
    drowsy_trigger_seconds: int
    distracted_trigger_seconds: int
    over_focus_window_minutes: int
    over_focus_threshold_minutes: int


class SettingsUpdate(BaseModel):
    working_hours_start: Optional[str] = None
    working_hours_end: Optional[str] = None
    max_notifications_per_day: Optional[int] = None
    camera_enabled: Optional[bool] = None
    camera_index: Optional[int] = None
    model_tier: Optional[str] = None
    sync_enabled: Optional[bool] = None
    drowsy_cooldown_minutes: Optional[int] = None
    distracted_cooldown_minutes: Optional[int] = None
    over_focus_cooldown_minutes: Optional[int] = None
    drowsy_trigger_seconds: Optional[int] = None
    distracted_trigger_seconds: Optional[int] = None
    over_focus_window_minutes: Optional[int] = None
    over_focus_threshold_minutes: Optional[int] = None


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
    return SettingsResponse(
        working_hours_start=config.working_hours_start,
        working_hours_end=config.working_hours_end,
        max_notifications_per_day=config.max_notifications_per_day,
        camera_enabled=config.camera_enabled,
        camera_index=config.camera_index,
        model_tier=config.model_tier,
        sync_enabled=config.sync_enabled,
        drowsy_cooldown_minutes=config.drowsy_cooldown_minutes,
        distracted_cooldown_minutes=config.distracted_cooldown_minutes,
        over_focus_cooldown_minutes=config.over_focus_cooldown_minutes,
        drowsy_trigger_seconds=config.drowsy_trigger_seconds,
        distracted_trigger_seconds=config.distracted_trigger_seconds,
        over_focus_window_minutes=config.over_focus_window_minutes,
        over_focus_threshold_minutes=config.over_focus_threshold_minutes,
    )


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

    return SettingsResponse(
        working_hours_start=config.working_hours_start,
        working_hours_end=config.working_hours_end,
        max_notifications_per_day=config.max_notifications_per_day,
        camera_enabled=config.camera_enabled,
        camera_index=config.camera_index,
        model_tier=config.model_tier,
        sync_enabled=config.sync_enabled,
        drowsy_cooldown_minutes=config.drowsy_cooldown_minutes,
        distracted_cooldown_minutes=config.distracted_cooldown_minutes,
        over_focus_cooldown_minutes=config.over_focus_cooldown_minutes,
        drowsy_trigger_seconds=config.drowsy_trigger_seconds,
        distracted_trigger_seconds=config.distracted_trigger_seconds,
        over_focus_window_minutes=config.over_focus_window_minutes,
        over_focus_threshold_minutes=config.over_focus_threshold_minutes,
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

    # For MVP, return local stats as the "report"
    # TODO: proxy to Cloud Run when sync_enabled
    stats["report"] = {
        "summary": f"本日の作業統計: 集中 {stats.get('focused_minutes', 0):.0f}分",
        "highlights": [],
        "concerns": [],
        "tomorrow_tip": "明日も頑張りましょう！",
    }
    return stats


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

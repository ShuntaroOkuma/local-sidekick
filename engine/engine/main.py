"""FastAPI entry point for the Local Sidekick Engine.

Runs on localhost:18080. Manages background monitoring tasks for:
- Camera capture + feature extraction + snapshot storage
- PC usage monitoring + snapshot storage
- Unified classification (rule-based -> LLM -> fallback)
- Notification evaluation
- History recording
- WebSocket broadcasting

Usage:
    python -m engine.main
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from engine.api.routes import router as api_router
from engine.api.routes import set_engine_state
from engine.api.websocket import (
    broadcast_notification,
    broadcast_state,
    router as ws_router,
)
from engine.config import EngineConfig, load_config
from engine.estimation.integrator import build_integrated_state
from engine.estimation.prompts import UNIFIED_SYSTEM_PROMPT, format_unified_prompt
from engine.estimation.rule_classifier import (
    ClassificationResult,
    classify_unified,
    classify_unified_fallback,
)
from engine.history.store import HistoryStore
from engine.notification.engine import NotificationEngine

logger = logging.getLogger(__name__)

# --- Global state ---

_monitoring_tasks: list[asyncio.Task] = []
_should_monitor = False
_paused = False  # True when system is suspended (e.g. lid closed)
_config: EngineConfig = EngineConfig()

# Latest raw snapshots (updated by camera/PC loops, consumed by integration loop)
_latest_camera_snapshot: Optional[dict] = None  # TrackerSnapshot.to_dict()
_latest_pc_snapshot: Optional[dict] = None  # UsageSnapshot.to_dict()

# Components
_history_store = HistoryStore()
_notification_engine: Optional[NotificationEngine] = None
_shared_llm_backend = None  # Shared LLM instance to avoid loading model twice
_llm_lock = asyncio.Lock()  # Lock for thread-safe LLM access


_llm_load_failed = False  # Avoid retrying when model file is missing


async def _get_shared_llm(config: EngineConfig):
    """Get or create the shared LLM backend (lazy-loaded, singleton).

    Uses _llm_lock to prevent concurrent initialization which could
    load the model (2-5GB) into memory twice.
    Returns None immediately when model_tier is "none" (rule-only mode)
    or when a previous load attempt already failed (model file missing).
    """
    global _shared_llm_backend, _llm_load_failed

    if config.model_tier == "none":
        return None

    if _llm_load_failed:
        return None

    if _shared_llm_backend is not None:
        return _shared_llm_backend

    async with _llm_lock:
        # Double-check after acquiring lock
        if _shared_llm_backend is not None:
            return _shared_llm_backend
        if _llm_load_failed:
            return None

        # Check if model file exists before attempting load
        from pathlib import Path
        from engine.config import get_text_model
        try:
            model_path = get_text_model("llama_cpp", tier=config.model_tier)
            if not Path(model_path).exists():
                logger.warning(
                    "Model file not found at %s, skipping LLM load.", model_path
                )
                _llm_load_failed = True
                return None
        except ValueError:
            _llm_load_failed = True
            return None

        try:
            from engine.estimation.llm_backend import LLMBackend
            backend = LLMBackend(
                model_tier=config.model_tier,
                n_ctx=config.llm_n_ctx,
            )
            await asyncio.to_thread(backend.load)
            _shared_llm_backend = backend
            return _shared_llm_backend
        except Exception as e:
            logger.warning("Failed to load shared LLM backend: %s", e)
            _llm_load_failed = True
            return None


def _create_notification_engine(config: EngineConfig) -> NotificationEngine:
    """Create a notification engine from config."""
    return NotificationEngine(
        drowsy_trigger_seconds=config.drowsy_trigger_seconds,
        distracted_trigger_seconds=config.distracted_trigger_seconds,
        over_focus_window_minutes=config.over_focus_window_minutes,
        over_focus_threshold_minutes=config.over_focus_threshold_minutes,
        drowsy_cooldown_minutes=config.drowsy_cooldown_minutes,
        distracted_cooldown_minutes=config.distracted_cooldown_minutes,
        over_focus_cooldown_minutes=config.over_focus_cooldown_minutes,
        max_notifications_per_day=config.max_notifications_per_day,
    )


# --- Camera monitoring ---


async def _camera_loop() -> None:
    """Background task: camera capture + feature extraction + snapshot storage.

    Runs at ~5fps (200ms interval) for frame capture. Stores raw snapshots
    every estimation_interval seconds for the integration loop to classify.
    Reads from global _config so settings changes take effect dynamically.
    """
    global _latest_camera_snapshot

    if not _config.camera_enabled:
        logger.info("Camera disabled in config, skipping camera loop.")
        return

    try:
        from engine.camera.capture import CameraCapture
        from engine.camera.features import FeatureTracker, extract_frame_features
    except ImportError as e:
        logger.error("Failed to import camera modules: %s", e)
        return

    try:
        camera = CameraCapture(camera_index=_config.camera_index)
        camera.open()
    except RuntimeError as e:
        logger.error("Failed to open camera: %s", e)
        return

    tracker = FeatureTracker()
    last_estimation = 0.0

    camera_open = True

    try:
        while _should_monitor:
            if _paused:
                # Release camera hardware so the green LED turns off
                if camera_open:
                    await asyncio.to_thread(camera.close)
                    camera_open = False
                    logger.info("Camera released for system sleep.")
                await asyncio.sleep(1.0)
                continue

            # Re-open camera after resume
            if not camera_open:
                try:
                    await asyncio.to_thread(camera.open)
                    camera_open = True
                    logger.info("Camera re-opened after resume.")
                except RuntimeError as e:
                    logger.warning("Camera re-open failed: %s", e)
                    await asyncio.sleep(2.0)
                    continue

            try:
                frame_result = await asyncio.to_thread(camera.read_frame)
            except RuntimeError:
                await asyncio.sleep(0.5)
                continue

            frame_features = extract_frame_features(
                frame_result.landmarks,
                frame_result.timestamp,
            )
            snapshot = tracker.update(frame_features)

            now = time.monotonic()
            if now - last_estimation >= _config.estimation_interval:
                last_estimation = now
                _latest_camera_snapshot = snapshot.to_dict()

            await asyncio.sleep(_config.camera_frame_interval)
    finally:
        if camera_open:
            camera.close()


# --- PC monitoring ---


async def _pc_monitor_loop() -> None:
    """Background task: PC usage monitoring + snapshot storage.

    PC monitor runs continuously; stores raw snapshots at pc_estimation_interval
    for the integration loop to classify.
    Reads from global _config so settings changes take effect dynamically.
    """
    global _latest_pc_snapshot

    try:
        from engine.pcusage.monitor import PCUsageMonitor
    except ImportError as e:
        logger.error("Failed to import PC usage monitor: %s", e)
        return

    monitor = PCUsageMonitor(window_seconds=60)
    monitor.start()

    last_estimation = 0.0

    try:
        while _should_monitor:
            if _paused:
                await asyncio.sleep(1.0)
                continue

            now = time.monotonic()
            if now - last_estimation >= _config.pc_estimation_interval:
                last_estimation = now

                try:
                    snapshot = monitor.take_snapshot()
                except Exception as e:
                    logger.warning("PC snapshot failed: %s", e)
                    await asyncio.sleep(_config.pc_poll_interval)
                    continue

                _latest_pc_snapshot = snapshot.to_dict()

            await asyncio.sleep(_config.pc_poll_interval)
    finally:
        monitor.stop()


# --- Integration + notification + history loop ---


async def _get_final_classification(
    camera_snap: Optional[dict], pc_snap: Optional[dict],
) -> ClassificationResult:
    """Run unified classification: rule -> LLM -> fallback.

    Returns a ClassificationResult (never None).
    """
    # 1. Unified rule-based classification (clear cases)
    rule_result = classify_unified(camera_snap, pc_snap)
    if rule_result is not None:
        return rule_result

    # 2. Unified LLM classification (ambiguous cases)
    llm = await _get_shared_llm(_config)
    if llm is None:
        return classify_unified_fallback(camera_snap, pc_snap)

    camera_json = json.dumps(camera_snap, indent=2) if camera_snap else "(unavailable)"
    pc_json = json.dumps(pc_snap, indent=2) if pc_snap else "(unavailable)"
    user_prompt = format_unified_prompt(camera_json, pc_json)

    try:
        async with _llm_lock:
            result = await asyncio.to_thread(
                llm.classify, UNIFIED_SYSTEM_PROMPT, user_prompt,
            )
        return ClassificationResult(
            state=result.get("state", "unknown"),
            confidence=result.get("confidence", 0.5),
            reasoning=result.get("reasoning", ""),
            source="llm",
        )
    except Exception as e:
        logger.error("Unified LLM inference failed: %s", e)
        return classify_unified_fallback(camera_snap, pc_snap)


async def _integration_loop() -> None:
    """Background task: unified classification, notifications, history.

    Consumes raw snapshots from camera/PC loops and runs unified
    classification (rule-based -> LLM -> fallback) to produce a single
    integrated state.
    Reads from global _config so settings changes take effect dynamically.
    """
    global _notification_engine

    _notification_engine = _create_notification_engine(_config)

    while _should_monitor:
        if _paused:
            await asyncio.sleep(1.0)
            continue

        camera_snap = _latest_camera_snapshot
        pc_snap = _latest_pc_snapshot

        # Early exit: avoid unnecessary LLM/rule calls when no data exists.
        # classify_unified also handles this, but skipping here saves a sleep cycle.
        if camera_snap is None and pc_snap is None:
            await asyncio.sleep(_config.integration_interval)
            continue

        final = await _get_final_classification(camera_snap, pc_snap)

        # Build IntegratedState (API-compatible wrapper)
        integrated = build_integrated_state(final, camera_snap, pc_snap)

        # Update shared state for API
        state_data = integrated.to_dict()
        set_engine_state("current_state", state_data)

        # Broadcast via WebSocket
        await broadcast_state(state_data)

        # Record to history
        await _history_store.log_state(
            timestamp=integrated.timestamp,
            camera_state=integrated.camera_state,
            pc_state=integrated.pc_state,
            integrated_state=integrated.state,
            confidence=integrated.confidence,
            source=final.source,
        )

        # Check for notifications
        notification = _notification_engine.evaluate(
            state=integrated.state,
            timestamp=integrated.timestamp,
            interval_seconds=_config.integration_interval,
        )

        if notification is not None:
            await _history_store.log_notification(
                timestamp=notification.timestamp,
                notification_type=notification.type,
                message=notification.message,
            )
            await broadcast_notification(
                notification_type=notification.type,
                message=notification.message,
                timestamp=notification.timestamp,
            )

        await asyncio.sleep(_config.integration_interval)


# --- Start/Stop callbacks ---


async def apply_config(new_config: EngineConfig) -> None:
    """Apply a new config to the running engine (called from settings API)."""
    global _config, _notification_engine, _llm_load_failed

    _config = new_config
    # Reset LLM load failure flag so tier change can trigger a new load attempt
    _llm_load_failed = False
    # Recreate notification engine with updated settings
    if _notification_engine is not None:
        _notification_engine = _create_notification_engine(_config)
    logger.info("Applied updated config to running engine.")


async def start_monitoring() -> None:
    """Start all monitoring background tasks."""
    global _should_monitor, _config, _latest_camera_snapshot, _latest_pc_snapshot

    if _should_monitor:
        return

    _config = load_config()
    _should_monitor = True
    _latest_camera_snapshot = None
    _latest_pc_snapshot = None

    set_engine_state("monitoring", True)
    set_engine_state("start_time", time.time())

    logger.info("Starting monitoring tasks...")

    tasks = [
        asyncio.create_task(_camera_loop(), name="camera_loop"),
        asyncio.create_task(_pc_monitor_loop(), name="pc_monitor_loop"),
        asyncio.create_task(_integration_loop(), name="integration_loop"),
    ]
    _monitoring_tasks.extend(tasks)


async def pause_monitoring() -> None:
    """Pause monitoring (e.g. system sleep). Loops stay alive but skip work."""
    global _paused

    if _paused or not _should_monitor:
        return

    _paused = True
    set_engine_state("paused", True)
    logger.info("Monitoring paused (system suspend).")


async def resume_monitoring() -> None:
    """Resume monitoring after pause. Resets consecutive state tracking."""
    global _paused, _latest_camera_snapshot, _latest_pc_snapshot

    if not _paused:
        return

    # Reset latest snapshots so stale data from before sleep isn't used
    _latest_camera_snapshot = None
    _latest_pc_snapshot = None

    # Reset notification engine consecutive state so sleep duration
    # doesn't count toward distracted/drowsy thresholds
    if _notification_engine is not None:
        _notification_engine.reset_consecutive()

    _paused = False
    set_engine_state("paused", False)
    logger.info("Monitoring resumed (system wake).")


async def stop_monitoring() -> None:
    """Stop all monitoring background tasks."""
    global _should_monitor, _shared_llm_backend

    _should_monitor = False
    set_engine_state("monitoring", False)

    logger.info("Stopping monitoring tasks...")

    for task in _monitoring_tasks:
        task.cancel()

    await asyncio.gather(*_monitoring_tasks, return_exceptions=True)
    _monitoring_tasks.clear()

    # Unload shared LLM backend
    if _shared_llm_backend is not None:
        try:
            await asyncio.to_thread(_shared_llm_backend.unload)
        except Exception:
            pass
        _shared_llm_backend = None

    logger.info("All monitoring tasks stopped.")


# --- Auto-download essential models on first launch ---


def _auto_download_essential_models() -> None:
    """Trigger background downloads for face_landmarker and lightweight model.

    Non-blocking: spawns a daemon thread so the engine starts immediately.
    Reuses the download functions from the models API module.
    """
    from engine.api.models import _is_model_downloaded, _download_worker, _download_lock, _download_state

    models_to_download = []
    if not _is_model_downloaded("face_landmarker"):
        models_to_download.append("face_landmarker")
    if not _is_model_downloaded("qwen2.5-3b"):
        models_to_download.append("qwen2.5-3b")

    if not models_to_download:
        logger.info("Essential models already downloaded.")
        return

    import threading

    def _download_all():
        for model_id in models_to_download:
            with _download_lock:
                _download_state[model_id] = {"status": "downloading", "error": None}
            _download_worker(model_id)

    logger.info("Auto-downloading essential models: %s", models_to_download)
    thread = threading.Thread(
        target=_download_all,
        daemon=True,
        name="auto-download-essential",
    )
    thread.start()


# --- FastAPI app ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: open history store, start monitoring."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    await _history_store.open()
    set_engine_state("history_store", _history_store)
    set_engine_state("start_callback", start_monitoring)
    set_engine_state("stop_callback", stop_monitoring)
    set_engine_state("pause_callback", pause_monitoring)
    set_engine_state("resume_callback", resume_monitoring)
    set_engine_state("apply_config_callback", apply_config)

    # Auto-download essential models in background on first launch
    _auto_download_essential_models()

    # Auto-start monitoring on launch
    await start_monitoring()

    yield

    # Shutdown
    await stop_monitoring()
    await _history_store.close()


app = FastAPI(
    title="Local Sidekick Engine",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: allow Electron renderer to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from engine.api.models import router as models_router

app.include_router(api_router)
app.include_router(ws_router)
app.include_router(models_router)


def main() -> None:
    """Run the engine server."""
    config = load_config()
    uvicorn.run(
        "engine.main:app",
        host="127.0.0.1",
        port=config.engine_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()

"""FastAPI entry point for the Local Sidekick Engine.

Runs on localhost:18080. Manages background monitoring tasks for:
- Camera capture + feature extraction + state estimation
- PC usage monitoring + state classification
- State integration (camera + PC)
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
from engine.estimation.integrator import StateIntegrator
from engine.estimation.rule_classifier import (
    ClassificationResult,
    classify_camera_text,
    classify_pc_usage,
)
from engine.history.store import HistoryStore
from engine.notification.engine import NotificationEngine

logger = logging.getLogger(__name__)

# --- Global state ---

_monitoring_tasks: list[asyncio.Task] = []
_should_monitor = False
_config: EngineConfig = EngineConfig()

# Latest classification results (updated by background tasks)
_latest_camera_state: Optional[ClassificationResult] = None
_latest_pc_state: Optional[ClassificationResult] = None

# Components
_history_store = HistoryStore()
_integrator = StateIntegrator()
_notification_engine: Optional[NotificationEngine] = None


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


async def _camera_loop(config: EngineConfig) -> None:
    """Background task: camera capture + feature extraction + classification.

    Runs at ~5fps (200ms interval) for frame capture, with state
    classification every estimation_interval seconds.
    """
    global _latest_camera_state

    if not config.camera_enabled:
        logger.info("Camera disabled in config, skipping camera loop.")
        return

    try:
        from engine.camera.capture import CameraCapture
        from engine.camera.features import FeatureTracker, extract_frame_features
    except ImportError as e:
        logger.error("Failed to import camera modules: %s", e)
        return

    llm_backend = None

    try:
        camera = CameraCapture(camera_index=config.camera_index)
        camera.open()
    except RuntimeError as e:
        logger.error("Failed to open camera: %s", e)
        return

    tracker = FeatureTracker()
    last_estimation = 0.0

    try:
        while _should_monitor:
            try:
                frame_result = camera.read_frame()
            except RuntimeError:
                await asyncio.sleep(0.5)
                continue

            frame_features = extract_frame_features(
                frame_result.landmarks,
                frame_result.timestamp,
            )
            snapshot = tracker.update(frame_features)

            now = time.monotonic()
            if now - last_estimation >= config.estimation_interval:
                last_estimation = now
                snapshot_dict = snapshot.to_dict()

                # Try rule-based classification first
                rule_result = classify_camera_text(snapshot_dict)
                if rule_result is not None:
                    _latest_camera_state = rule_result
                else:
                    # LLM fallback
                    if llm_backend is None:
                        try:
                            from engine.estimation.llm_backend import LLMBackend
                            from engine.estimation.prompts import (
                                TEXT_SYSTEM_PROMPT,
                                format_text_prompt,
                            )

                            llm_backend = LLMBackend(
                                model_tier=config.model_tier,
                                n_ctx=config.llm_n_ctx,
                            )
                            llm_backend.load()
                        except Exception as e:
                            logger.warning("LLM backend unavailable: %s", e)
                            # Default to focused with low confidence
                            _latest_camera_state = ClassificationResult(
                                state="focused",
                                confidence=0.5,
                                reasoning="LLM unavailable, defaulting",
                                source="fallback",
                            )
                            continue

                    from engine.estimation.prompts import (
                        TEXT_SYSTEM_PROMPT,
                        format_text_prompt,
                    )

                    features_json = snapshot.to_json()
                    user_prompt = format_text_prompt(features_json)

                    try:
                        result = await asyncio.to_thread(
                            llm_backend.classify,
                            TEXT_SYSTEM_PROMPT,
                            user_prompt,
                        )
                        _latest_camera_state = ClassificationResult(
                            state=result.get("state", "unknown"),
                            confidence=result.get("confidence", 0.5),
                            reasoning=result.get("reasoning", ""),
                            source="llm",
                        )
                    except Exception as e:
                        logger.error("LLM inference failed: %s", e)

            await asyncio.sleep(config.camera_frame_interval)
    finally:
        camera.close()
        if llm_backend is not None:
            llm_backend.unload()


# --- PC monitoring ---


async def _pc_monitor_loop(config: EngineConfig) -> None:
    """Background task: PC usage monitoring + classification.

    PC monitor runs continuously; snapshots taken at pc_estimation_interval.
    """
    global _latest_pc_state

    try:
        from engine.pcusage.monitor import PCUsageMonitor
    except ImportError as e:
        logger.error("Failed to import PC usage monitor: %s", e)
        return

    monitor = PCUsageMonitor(window_seconds=60)
    monitor.start()

    llm_backend = None
    last_estimation = 0.0

    try:
        while _should_monitor:
            now = time.monotonic()
            if now - last_estimation >= config.pc_estimation_interval:
                last_estimation = now
                snapshot = monitor.take_snapshot()
                snapshot_dict = snapshot.to_dict()

                # Try rule-based classification first
                rule_result = classify_pc_usage(snapshot_dict)
                if rule_result is not None:
                    _latest_pc_state = rule_result
                else:
                    # LLM fallback for PC
                    if llm_backend is None:
                        try:
                            from engine.estimation.llm_backend import LLMBackend
                            llm_backend = LLMBackend(
                                model_tier=config.model_tier,
                                n_ctx=config.llm_n_ctx,
                            )
                            llm_backend.load()
                        except Exception as e:
                            logger.warning("LLM backend unavailable for PC: %s", e)
                            _latest_pc_state = ClassificationResult(
                                state="focused",
                                confidence=0.5,
                                reasoning="LLM unavailable, defaulting",
                                source="fallback",
                            )
                            continue

                    from engine.estimation.prompts import (
                        PC_USAGE_SYSTEM_PROMPT,
                        format_pc_usage_prompt,
                    )

                    usage_json = json.dumps(snapshot_dict, indent=2)
                    user_prompt = format_pc_usage_prompt(usage_json)

                    try:
                        result = await asyncio.to_thread(
                            llm_backend.classify,
                            PC_USAGE_SYSTEM_PROMPT,
                            user_prompt,
                        )
                        _latest_pc_state = ClassificationResult(
                            state=result.get("state", "unknown"),
                            confidence=result.get("confidence", 0.5),
                            reasoning=result.get("reasoning", ""),
                            source="llm",
                        )
                    except Exception as e:
                        logger.error("LLM inference failed for PC: %s", e)

            await asyncio.sleep(config.pc_poll_interval)
    finally:
        monitor.stop()
        if llm_backend is not None:
            llm_backend.unload()


# --- Integration + notification + history loop ---


async def _integration_loop(config: EngineConfig) -> None:
    """Background task: integrate states, check notifications, record history."""
    global _notification_engine

    _notification_engine = _create_notification_engine(config)

    while _should_monitor:
        camera_state = _latest_camera_state
        pc_state = _latest_pc_state

        integrated = _integrator.integrate(
            camera_state=camera_state.state if camera_state else None,
            camera_confidence=camera_state.confidence if camera_state else 0.0,
            pc_state=pc_state.state if pc_state else None,
            pc_confidence=pc_state.confidence if pc_state else 0.0,
        )

        # Update shared state for API
        state_data = integrated.to_dict()
        set_engine_state("current_state", state_data)

        # Broadcast via WebSocket
        await broadcast_state(state_data)

        # Record to history
        source = "rule"
        if camera_state and camera_state.source == "llm":
            source = "llm"
        elif pc_state and pc_state.source == "llm":
            source = "llm"

        await _history_store.log_state(
            timestamp=integrated.timestamp,
            camera_state=integrated.camera_state,
            pc_state=integrated.pc_state,
            integrated_state=integrated.state,
            confidence=integrated.confidence,
            source=source,
        )

        # Check for notifications
        notification = _notification_engine.evaluate(
            state=integrated.state,
            timestamp=integrated.timestamp,
            interval_seconds=config.integration_interval,
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

        await asyncio.sleep(config.integration_interval)


# --- Start/Stop callbacks ---


async def start_monitoring() -> None:
    """Start all monitoring background tasks."""
    global _should_monitor, _config, _latest_camera_state, _latest_pc_state

    if _should_monitor:
        return

    _config = load_config()
    _should_monitor = True
    _latest_camera_state = None
    _latest_pc_state = None

    set_engine_state("monitoring", True)
    set_engine_state("start_time", time.time())

    logger.info("Starting monitoring tasks...")

    tasks = [
        asyncio.create_task(_camera_loop(_config), name="camera_loop"),
        asyncio.create_task(_pc_monitor_loop(_config), name="pc_monitor_loop"),
        asyncio.create_task(_integration_loop(_config), name="integration_loop"),
    ]
    _monitoring_tasks.extend(tasks)


async def stop_monitoring() -> None:
    """Stop all monitoring background tasks."""
    global _should_monitor

    _should_monitor = False
    set_engine_state("monitoring", False)

    logger.info("Stopping monitoring tasks...")

    for task in _monitoring_tasks:
        task.cancel()

    await asyncio.gather(*_monitoring_tasks, return_exceptions=True)
    _monitoring_tasks.clear()

    logger.info("All monitoring tasks stopped.")


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

app.include_router(api_router)
app.include_router(ws_router)


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

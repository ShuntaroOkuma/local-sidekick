"""WebSocket endpoint for real-time state broadcasting.

Provides /ws/state endpoint that pushes:
- State changes: {"state": "focused", "confidence": 0.9, ...}
- Notifications: {"type": "notification", "notification_type": "drowsy", ...}
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.info(
            "WebSocket client connected. Total: %d", len(self._connections)
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.info(
            "WebSocket client disconnected. Total: %d", len(self._connections)
        )

    async def broadcast(self, data: dict) -> None:
        """Send a JSON message to all connected clients.

        Disconnected clients are automatically cleaned up.
        """
        message = json.dumps(data)
        disconnected: list[WebSocket] = []

        async with self._lock:
            connections = list(self._connections)

        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)

        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    if ws in self._connections:
                        self._connections.remove(ws)

    @property
    def connection_count(self) -> int:
        """Number of active connections."""
        return len(self._connections)


# Singleton connection manager
manager = ConnectionManager()


@router.websocket("/ws/state")
async def websocket_state(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time state updates.

    Clients connect and receive JSON messages:
    - State updates: {"state": ..., "confidence": ..., "camera_state": ..., "pc_state": ..., "timestamp": ...}
    - Notifications: {"type": "notification", "notification_type": ..., "message": ..., "timestamp": ...}
    """
    await manager.connect(websocket)
    try:
        # Keep the connection alive; listen for client messages (e.g., pings)
        while True:
            try:
                data = await websocket.receive_text()
                # Clients can send ping/pong or other messages
                if data == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
    finally:
        await manager.disconnect(websocket)


async def broadcast_state(state_data: dict) -> None:
    """Broadcast a state update to all connected WebSocket clients.

    Args:
        state_data: Dict with state, confidence, camera_state, pc_state, timestamp.
    """
    await manager.broadcast(state_data)


async def broadcast_notification(
    notification_type: str,
    message: str,
    timestamp: float,
) -> None:
    """Broadcast a notification event to all connected WebSocket clients.

    Args:
        notification_type: Type of notification (drowsy, distracted, over_focus).
        message: Notification message text.
        timestamp: When the notification was triggered.
    """
    await manager.broadcast({
        "type": "notification",
        "notification_type": notification_type,
        "message": message,
        "timestamp": timestamp,
    })

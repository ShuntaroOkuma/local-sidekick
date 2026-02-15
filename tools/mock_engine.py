"""Mock Engine - sends state changes via WebSocket for avatar testing.

Provides stub responses for all API endpoints the client expects,
so the Electron app can run without the real engine.
"""
import asyncio
import json
import time
from typing import Optional

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Store for connected WebSocket clients
clients: list[WebSocket] = []
current_state = {"state": "focused", "confidence": 0.5, "timestamp": time.time()}

# Pending notifications queue (consumed by Electron polling)
pending_notifications_queue: list[dict] = []

# Mock settings (mirrors engine SettingsResponse)
mock_settings = {
    "camera_enabled": False,
    "camera_index": 0,
    "model_tier": "lightweight",
    "sync_enabled": False,
    "avatar_enabled": True,
    "drowsy_cooldown_minutes": 5,
    "distracted_cooldown_minutes": 3,
    "over_focus_cooldown_minutes": 25,
    "drowsy_trigger_buckets": 2,
    "distracted_trigger_buckets": 2,
    "over_focus_window_buckets": 6,
    "over_focus_threshold_buckets": 5,
    "cloud_run_url": "",
    "cloud_auth_email": "",
}

# Mock model list (mirrors engine ModelInfo)
mock_models = [
    {
        "id": "qwen2.5-3b",
        "name": "軽量モデル (3B)",
        "description": "高速、省メモリ。基本的な判定に最適",
        "size_gb": 2.0,
        "tier": "lightweight",
        "downloaded": True,
        "downloading": False,
        "error": None,
    },
    {
        "id": "qwen2.5-7b",
        "name": "高性能モデル (7B)",
        "description": "高精度。より正確な状態判定",
        "size_gb": 4.7,
        "tier": "recommended",
        "downloaded": False,
        "downloading": False,
        "error": None,
    },
    {
        "id": "face_landmarker",
        "name": "顔認識モデル",
        "description": "カメラによる状態検知に必要",
        "size_gb": 0.004,
        "tier": "vision",
        "downloaded": False,
        "downloading": False,
        "error": None,
    },
]

monitoring = True


# --- Real API endpoints (matching engine routes) ---


@app.get("/api/health")
async def health():
    return {"status": "ok", "monitoring": monitoring, "uptime_seconds": 0}


@app.get("/api/state")
async def get_state():
    return current_state


@app.get("/api/settings")
async def get_settings():
    return mock_settings


@app.put("/api/settings")
async def update_settings(body: dict):
    for key, value in body.items():
        if key in mock_settings:
            mock_settings[key] = value
    return mock_settings


@app.get("/api/models")
async def list_models():
    return mock_models


@app.post("/api/models/{model_id}/download")
async def download_model(model_id: str):
    return {"status": "ok", "message": "Mock: ダウンロードをスキップしました"}


@app.delete("/api/models/{model_id}")
async def delete_model(model_id: str):
    return {"status": "ok", "message": "Mock: モデルを削除しました"}


@app.get("/api/history")
async def get_history(start: Optional[float] = None, end: Optional[float] = None):
    return {"state_log": [], "notifications": [], "count": 0}


@app.get("/api/history/bucketed")
async def get_history_bucketed(start: float = 0, end: float = 0, bucket_minutes: int = 5):
    return {"segments": [], "count": 0}


@app.get("/api/daily-stats")
async def get_daily_stats(date: Optional[str] = None):
    return {
        "date": date or time.strftime("%Y-%m-%d"),
        "focused_minutes": 0,
        "drowsy_minutes": 0,
        "distracted_minutes": 0,
        "away_minutes": 0,
        "total_minutes": 0,
        "notification_count": 0,
        "report": None,
        "report_text": None,
    }


@app.get("/api/notifications")
async def get_notifications(start: Optional[float] = None, end: Optional[float] = None):
    return []


@app.get("/api/notifications/pending")
async def pending_notifications():
    """Return and drain pending notifications (consumed by Electron polling)."""
    notifications = list(pending_notifications_queue)
    pending_notifications_queue.clear()
    return notifications


@app.get("/api/reports")
async def list_reports():
    return {"dates": []}


@app.get("/api/reports/{date}")
async def get_report(date: str):
    return {"date": date, "report": None}


@app.post("/api/reports/generate")
async def generate_report(date: Optional[str] = None):
    d = date or time.strftime("%Y-%m-%d")
    return {
        "date": d,
        "focused_minutes": 0,
        "drowsy_minutes": 0,
        "distracted_minutes": 0,
        "away_minutes": 0,
        "total_minutes": 0,
        "notification_count": 0,
        "report": {
            "summary": "Mock: データなし",
            "highlights": [],
            "concerns": [],
            "tomorrow_tip": "明日も頑張りましょう！",
        },
        "report_source": "mock",
    }


@app.post("/api/engine/start")
async def start_engine():
    global monitoring
    monitoring = True
    return {"status": "ok", "message": "Monitoring started"}


@app.post("/api/engine/stop")
async def stop_engine():
    global monitoring
    monitoring = False
    return {"status": "ok", "message": "Monitoring stopped"}


@app.post("/api/cloud/check-url")
async def cloud_check_url(body: dict):
    return {"status": "ok"}


@app.post("/api/cloud/login")
async def cloud_login(body: dict):
    return {"status": "ok", "email": body.get("email", "")}


@app.post("/api/cloud/register")
async def cloud_register(body: dict):
    return {"status": "ok", "email": body.get("email", "")}


@app.post("/api/cloud/logout")
async def cloud_logout():
    return {"status": "ok"}


# --- WebSocket ---


@app.websocket("/ws/state")
async def ws_state(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)
    print(f"Client connected. Total: {len(clients)}")
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except:
        clients.remove(websocket)
        print(f"Client disconnected. Total: {len(clients)}")


async def broadcast(data: dict):
    msg = json.dumps(data)
    for ws in list(clients):
        try:
            await ws.send_text(msg)
        except:
            clients.remove(ws)


# --- Test helper endpoints ---


@app.post("/test/state/{state_name}")
async def set_state(state_name: str):
    """Set state: focused, drowsy, distracted, away"""
    current_state.update({"state": state_name, "confidence": 0.9, "timestamp": time.time()})
    await broadcast(current_state)
    return {"set": state_name}


@app.post("/test/notification/{notif_type}")
async def send_notification(notif_type: str):
    """Send notification: drowsy, distracted, over_focus"""
    messages = {
        "drowsy": "眠気が来ています！立ちましょう",
        "distracted": "集中が途切れています",
        "over_focus": "休憩しませんか？",
    }
    data = {
        "type": "notification",
        "notification_type": notif_type,
        "message": messages.get(notif_type, notif_type),
        "timestamp": time.time(),
    }
    await broadcast(data)
    # Also enqueue for Electron HTTP polling (/api/notifications/pending)
    pending_notifications_queue.append({
        "type": notif_type,
        "message": data["message"],
        "timestamp": data["timestamp"],
    })
    return {"sent": notif_type}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=18080)

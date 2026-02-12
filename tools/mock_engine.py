"""Mock Engine - sends state changes via WebSocket for avatar testing."""
import asyncio
import json
import time
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Store for connected WebSocket clients
clients: list[WebSocket] = []
current_state = {"state": "idle", "confidence": 0.5, "timestamp": time.time()}

@app.get("/api/health")
async def health():
    return {"status": "ok", "monitoring": True, "uptime_seconds": 0}

@app.get("/api/state")
async def get_state():
    return current_state

@app.get("/api/notifications/pending")
async def pending_notifications():
    return []

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

@app.post("/test/state/{state_name}")
async def set_state(state_name: str):
    """Set state: focused, drowsy, distracted, away, idle"""
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
    return {"sent": notif_type}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=18080)

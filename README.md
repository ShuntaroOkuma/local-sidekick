# Local Sidekick

An always-on macOS observer that detects drowsiness, focus, and distraction using on-device camera analysis and PC usage monitoring -- then nudges you back on track with timely notifications and a daily AI-generated report.

## Architecture

```
macOS Electron App
  ├── Main Process (Tray, Notifications, Python Bridge)
  ├── Renderer (React: Dashboard, Timeline, Report, Settings)
  ├── Avatar Overlay (Transparent BrowserWindow, CSS character)
  └── Python Engine (FastAPI @ localhost:18080)
        ├── Camera Pipeline (MediaPipe face landmarks)
        ├── PC Usage Monitor (pynput + pyobjc)
        ├── Rule Classifier (95%) + LLM Fallback (5%)
        ├── State Integrator (camera + PC → final state)
        ├── Notification Engine (drowsy / distracted / over-focus)
        └── History Store (SQLite)

Google Cloud
  ├── Cloud Run API (FastAPI, JWT auth)
  ├── Vertex AI Gemini 2.5 Flash (daily report generation)
  └── Firestore (user settings, stats, reports)
```

## Directory Structure

```
local-sidekick/
├── client/                   # Electron + React app
│   ├── electron/             # Main process (tray, preload, python-bridge, notification, avatar-window)
│   ├── src/                  # React renderer
│   │   ├── pages/            # Dashboard, Timeline, Report, Settings
│   │   ├── components/       # StateIndicator, TimelineChart, etc.
│   │   ├── hooks/            # useEngineState, useSettings
│   │   ├── avatar/           # Avatar overlay (character, state machine, animations)
│   │   └── lib/              # api client, types
│   └── package.json
├── engine/                   # Python local backend
│   ├── engine/
│   │   ├── api/              # REST routes + WebSocket
│   │   ├── camera/           # capture + feature extraction
│   │   ├── estimation/       # rule_classifier, llm_backend, integrator
│   │   ├── pcusage/          # OS-level activity monitor
│   │   ├── notification/     # trigger logic (3 notification types)
│   │   ├── history/          # SQLite store + daily aggregator
│   │   ├── main.py           # FastAPI entry point
│   │   └── config.py         # centralized config
│   └── pyproject.toml
├── server/                   # Cloud Run API
│   ├── server/
│   │   ├── api/              # settings, statistics, reports
│   │   ├── services/         # vertex_ai, firestore_client
│   │   ├── models/           # Pydantic schemas
│   │   ├── auth.py           # JWT authentication
│   │   ├── deps.py           # shared Firestore singleton
│   │   └── main.py           # FastAPI entry point
│   ├── Dockerfile
│   └── pyproject.toml
├── poc/                      # Proof of Concept (reference, not modified)
├── docs/
│   ├── architecture.md       # Detailed MVP design
│   ├── requirements.md       # Product requirements
│   ├── manual-testing.md     # Verification procedures
│   └── poc-plan.md           # PoC experiment plan
└── README.md
```

## Quick Start

### Prerequisites

- macOS with Apple Silicon (M3/M4, 16GB+ RAM)
- Python 3.12+
- Node.js 20+

### 1. Engine

```bash
cd engine
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# (Optional) Download models for camera + LLM
python models/download.py

python -m engine.main
# → http://localhost:18080
```

### 2. Client

```bash
cd client
npm install
npm run dev
# → Electron app launches with tray icon
```

### 3. Server (optional, for cloud sync)

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

USE_MEMORY_STORE=true JWT_SECRET=dev-secret uvicorn server.main:app --port 8081
# → http://localhost:8081
```

### 3a. Server with Docker (recommended for integration testing)

Runs the same Docker image as Cloud Run, with a Firestore Emulator for realistic testing.

```bash
cd server
docker compose up --build
# → API: http://localhost:8080
# → Firestore Emulator: http://localhost:8086
```

Vertex AI uses a dummy fallback by default. To enable real Vertex AI:

```bash
gcloud auth application-default login
GCP_PROJECT_ID=your-project docker compose -f docker-compose.yml -f docker-compose.vertex.yml up --build
```

Stop and clean up:

```bash
docker compose down
```

## Key Features

| Feature                    | Description                                                                      |
| -------------------------- | -------------------------------------------------------------------------------- |
| Real-time state estimation | Camera (face landmarks) + PC usage → focused / drowsy / distracted / away / idle |
| 3 notification types       | Drowsy (120s), Distracted (120s), Over-focus (80min in 90min window)             |
| Desktop avatar             | Always-on-top animated character that reacts to your state in real-time           |
| Dashboard                  | Live state display, confidence bar, today's summary                              |
| Timeline                   | Color-coded hourly state visualization                                           |
| Daily Report               | AI-generated summary via Vertex AI (Gemini 2.5 Flash)                            |
| Settings sync              | Cloud Run API with JWT auth + Firestore                                          |
| Privacy-first              | All video processed on-device, only statistics sent to cloud                     |

## Avatar Overlay

A small animated character that lives on your desktop and reacts to your current state in real-time.

### How it works

- Runs in a transparent, always-on-top `BrowserWindow` (separate from the main app)
- Connects directly to the Engine WebSocket (`/ws/state`) for real-time state and notification updates
- Maps Engine states to avatar animations via a state machine with debouncing

### Avatar modes

| Engine State | Avatar Mode | Behavior                                           |
| ------------ | ----------- | -------------------------------------------------- |
| focused      | hidden      | Character retreats and hides (you're in the zone)  |
| idle         | peek        | Peeks in from the side                             |
| drowsy       | dozing      | Gentle breathing animation with ZZZ effect         |
| distracted   | wake-up     | Bounces in to get your attention                   |
| away         | peek        | Peeks in, waiting for you to return                |

Notifications from the Engine (drowsy, distracted, over-focus) are displayed as speech bubbles above the character, replacing OS-level notifications while the avatar is active.

### Settings

The avatar can be toggled ON/OFF from **Settings > アバター** in the GUI. When turned off, the avatar window is hidden and notifications fall back to OS-level notifications.

## Tech Stack

| Layer         | Technology                                    |
| ------------- | --------------------------------------------- |
| Desktop       | Electron 34 + React 19 + TypeScript           |
| Build         | electron-vite + Vite 6 + TailwindCSS 4        |
| Engine        | Python 3.12 + FastAPI + aiosqlite             |
| Camera        | OpenCV + MediaPipe Face Landmarks             |
| On-device LLM | llama-cpp-python + Qwen2.5-3B (Q4_K_M, Metal) |
| PC Monitor    | pynput + pyobjc                               |
| Cloud API     | Cloud Run + FastAPI                           |
| AI            | Vertex AI (Gemini 2.5 Flash)                  |
| Database      | Firestore (cloud) + SQLite (local)            |
| Auth          | JWT (python-jose + passlib)                   |

## Privacy

- No video leaves the device (default)
- No keystroke content recorded (only event counts)
- No screen capture
- Server receives only aggregated statistics
- Camera can be disabled in settings
- Avatar can be disabled in settings

## Documentation

- [Product Requirements](docs/requirements.md)
- [Architecture & Design](docs/architecture.md)
- [Manual Testing Guide](docs/manual-testing.md)
- [PoC Experiment Plan](docs/poc-plan.md)

## License

Private - Google Cloud Japan AI Hackathon Vol.4

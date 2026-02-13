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
├── tools/                    # Development & testing utilities
│   └── mock_engine.py        # Mock Engine for avatar testing (WebSocket + REST)
├── poc/                      # Proof of Concept (reference, not modified)
├── docs/
│   ├── architecture.md       # Detailed MVP design
│   └── manual-testing.md     # Verification procedures
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

## セキュリティに関する注意

- Cloud Run認証トークン（JWT）は `~/.local-sidekick/config.json` にプレーンテキストで保存されます
- 本実装はハッカソンデモ用の暫定実装です。本番運用ではシステムキーチェーン等の安全なストレージに移行が必要です
- `config.json` をバージョン管理に含めないでください（`.gitignore` で除外済み）

## GCP デプロイ（Cloud Run）

### 前提条件

```bash
gcloud auth login

# 以降の手順で使用する環境変数を設定
export PROJECT_ID=your-project-id
export REGION=asia-northeast1

gcloud config set project $PROJECT_ID

# 必要な API を有効化
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  firestore.googleapis.com
```

### IAM 権限設定（初回のみ）

```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

# Cloud Build がソースを GCS にアップロードするための権限
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/storage.admin"

# Cloud Build が Docker イメージを Artifact Registry に push するための権限
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Cloud Build が Cloud Run にデプロイするための権限
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/run.admin"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Cloud Run から Vertex AI を呼び出すための権限
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# Cloud Run から Firestore にアクセスするための権限
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/datastore.user"
```

### Artifact Registry リポジトリ作成（初回のみ）

```bash
gcloud artifacts repositories create local-sidekick \
  --repository-format=docker \
  --location=$REGION
```

### Firestore データベース作成（初回のみ）

```bash
gcloud firestore databases create --location=$REGION
```

### デプロイ

```bash
# リポジトリルートから実行（Dockerfile が server/ を COPY するため）
gcloud builds submit \
  --config=server/deploy/cloudbuild.yaml \
  --project=$PROJECT_ID \
  .
```

### 環境変数の設定

```bash
# JWT_SECRET を生成
export JWT_SECRET=$(openssl rand -base64 32)

gcloud run services update local-sidekick-api \
  --region=$REGION \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,GCP_LOCATION=$REGION,JWT_SECRET=$JWT_SECRET,ENV=production"
```

### デプロイ確認

```bash
# Cloud Run の URL を取得
SERVICE_URL=$(gcloud run services describe local-sidekick-api \
  --region=$REGION \
  --format='value(status.url)')

# ヘルスチェック
curl -s $SERVICE_URL/api/health
# → {"status": "ok", "service": "local-sidekick-api"}
```

### アプリから接続

1. Engine + Client を起動
2. Settings → サーバ同期 ON
3. Cloud Run URL に `$SERVICE_URL` を入力して保存
4. メール/パスワードでログインまたは新規登録
5. Report タブでレポート生成 → Vertex AI の AI レポートが返る

### 注意事項

- リージョン: デフォルト `asia-northeast1`（東京）。`$REGION` で変更可能
- `--allow-unauthenticated` で公開設定（アプリレベルで JWT 認証）
- 初回リクエストはコールドスタートで 10-30 秒かかる（Engine 側タイムアウト 60 秒）
- Cloud Run / Vertex AI ともに従量課金（リクエストがなければほぼ無料）

## Documentation

- [Architecture & Design](docs/architecture.md)
- [Manual Testing Guide](docs/manual-testing.md)

## License

MIT License. See LICENSE file for details.

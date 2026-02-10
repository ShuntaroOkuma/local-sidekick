# Local Sidekick MVP 設計書

## Context

PoCフェーズで llama-cpp-python + Qwen2.5-3B（テキストモード）による状態推定が~90%の精度で動作することを確認済み。ハッカソン提出期限(2/15)まで残り4-5日、2-3人チームでMVPを開発する。

### 制約

- **期限**: 2026/2/15（残り4-5日）
- **チーム**: 2-3人
- **ハッカソン要件**: Google Cloud アプリ実行プロダクト + AI技術
  - Cloud Run（バックエンドAPI）
  - Vertex AI（Gemini）必須
- **提出物**: GitHub / デプロイURL / Zenn記事

---

## 1. システムアーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│  macOS Electron App                                         │
│  ┌──────────────────┐    ┌──────────────────────────────┐  │
│  │  Main Process     │    │  Renderer (React)            │  │
│  │  - Tray/Menubar   │    │  - Dashboard (状態表示)      │  │
│  │  - Notifications  │◄──►│  - Timeline (時系列)         │  │
│  │  - Python子プロセス│    │  - Report (日次レポート)     │  │
│  │    管理           │    │  - Settings (設定)           │  │
│  └────────┬─────────┘    └──────────────────────────────┘  │
│           │ spawn & HTTP/WebSocket                          │
│  ┌────────▼──────────────────────────────────────────────┐  │
│  │  Python Engine (FastAPI) localhost:18080               │  │
│  │  ┌──────────┐ ┌───────────┐ ┌────────────────────┐   │  │
│  │  │ Camera   │ │ PC Usage  │ │ State Integrator   │   │  │
│  │  │ Pipeline │ │ Monitor   │ │ (camera+PC→最終判定)│   │  │
│  │  └────┬─────┘ └─────┬─────┘ └──────────┬─────────┘   │  │
│  │       │             │                   │              │  │
│  │  ┌────▼─────────────▼───────────────────▼──────────┐  │  │
│  │  │ Rule Classifier (95%) → LLM Fallback (5%)       │  │  │
│  │  │ llama-cpp-python + Qwen2.5-3B (Q4_K_M, Metal)  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  │                                                        │  │
│  │  ┌───────────────┐  ┌──────────────────┐              │  │
│  │  │ Notification  │  │ State History    │              │  │
│  │  │ Engine        │  │ (SQLite)         │              │  │
│  │  └───────────────┘  └──────────────────┘              │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTPS (統計・設定同期)
┌──────────────────────────▼───────────────────────────────────┐
│  Google Cloud                                                 │
│  ┌──────────────────┐   ┌────────────────────┐               │
│  │  Cloud Run        │   │  Vertex AI (Gemini)│               │
│  │  (FastAPI)        │──►│  - 日次レポート生成│               │
│  │  - 認証 (JWT)     │   │  - 改善提案        │               │
│  │  - 設定同期       │   └────────────────────┘               │
│  │  - 統計受信       │                                        │
│  │  - レポート生成   │                                        │
│  └────────┬─────────┘                                        │
│  ┌────────▼─────────┐                                        │
│  │  Firestore        │                                        │
│  │  - users          │                                        │
│  │  - settings       │                                        │
│  │  - daily_stats    │                                        │
│  └──────────────────┘                                        │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. ディレクトリ構成

```
local-sidekick/
├── docs/
│   ├── requirements.md          # 既存
│   ├── poc-plan.md              # 既存
│   └── architecture.md          # 本設計書
├── poc/                         # 既存PoC（参照用、変更しない）
│
├── client/                      # Electron アプリ
│   ├── package.json
│   ├── tsconfig.json
│   ├── electron-builder.json
│   ├── electron/
│   │   ├── main.ts              # Electronメインプロセス
│   │   ├── tray.ts              # メニューバー/トレイ
│   │   ├── preload.ts           # プリロードスクリプト
│   │   ├── python-bridge.ts     # Pythonプロセス管理
│   │   └── notification.ts      # macOS通知送信
│   ├── src/                     # React レンダラー
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx    # リアルタイム状態表示
│   │   │   ├── Timeline.tsx     # 今日のタイムライン
│   │   │   ├── Report.tsx       # 日次レポート表示
│   │   │   └── Settings.tsx     # 設定画面
│   │   ├── components/
│   │   │   ├── StateIndicator.tsx
│   │   │   ├── TimelineChart.tsx
│   │   │   └── NotificationCard.tsx
│   │   ├── hooks/
│   │   │   ├── useEngineState.ts   # WebSocket接続
│   │   │   └── useSettings.ts
│   │   └── lib/
│   │       ├── api.ts           # Python Engine API client
│   │       └── types.ts         # 共通型定義
│   └── public/
│       └── icon.png
│
├── engine/                      # Python ローカルバックエンド
│   ├── pyproject.toml
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI エントリポイント
│   │   ├── config.py            # 設定管理
│   │   ├── camera/
│   │   │   ├── __init__.py
│   │   │   ├── capture.py       # ← poc/shared/camera.py
│   │   │   └── features.py      # ← poc/shared/features.py
│   │   ├── estimation/
│   │   │   ├── __init__.py
│   │   │   ├── rule_classifier.py  # ← poc/shared/rule_classifier.py
│   │   │   ├── llm_backend.py     # llama-cpp-python wrapper
│   │   │   ├── prompts.py         # ← poc/shared/prompts.py
│   │   │   └── integrator.py      # カメラ+PC統合判定
│   │   ├── pcusage/
│   │   │   ├── __init__.py
│   │   │   └── monitor.py         # ← poc/experiment3_pcusage/monitor.py
│   │   ├── notification/
│   │   │   ├── __init__.py
│   │   │   └── engine.py          # 通知トリガーロジック
│   │   ├── history/
│   │   │   ├── __init__.py
│   │   │   ├── store.py           # SQLite 履歴保存
│   │   │   └── aggregator.py      # 日次集計
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── routes.py          # REST API
│   │       └── websocket.py       # WebSocket (状態配信)
│   └── models/                    # GGUFモデル + MediaPipe
│       ├── .gitkeep
│       └── download.py
│
├── server/                        # Cloud Run API
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── server/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI エントリポイント
│   │   ├── auth.py                # Firebase Auth / JWT
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── settings.py        # 設定同期 CRUD
│   │   │   ├── statistics.py      # 統計受信
│   │   │   └── reports.py         # 日次レポート
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── vertex_ai.py       # Vertex AI (Gemini) 連携
│   │   │   └── firestore.py       # Firestore クライアント
│   │   └── models/
│   │       ├── __init__.py
│   │       └── schemas.py         # Pydantic モデル
│   └── deploy/
│       └── cloudbuild.yaml
│
└── README.md
```

---

## 3. コンポーネント詳細設計

### 3.1 Python Engine (localhost:18080)

PoCのコードを再構成して常駐サービス化する。

#### エントリポイント: `engine/main.py`

```python
# FastAPI app with:
# - /api/state           GET  → 現在の状態
# - /api/history         GET  → 履歴データ
# - /api/settings        GET/PUT → ローカル設定
# - /api/daily-stats     GET  → 日次集計
# - /ws/state            WS   → リアルタイム状態配信
# - /api/engine/start    POST → 監視開始
# - /api/engine/stop     POST → 監視停止
```

#### メインループ（バックグラウンドタスク）

```
1. カメラスレッド: 200ms間隔でフレーム取得 + MediaPipe特徴量抽出
2. 推定スレッド: 5秒間隔で状態推定（Rule→LLMフォールバック）
3. PC監視スレッド: 2秒間隔でアプリポーリング + pynputリスナー
4. PC推定: 30秒間隔でPC状態分類
5. 統合判定: 5秒間隔でカメラ+PC結果を統合
6. 通知チェック: 統合結果をもとに通知条件判定
7. 履歴保存: 5秒ごとの状態をSQLiteに記録
8. WebSocket配信: 状態変化時にElectronへプッシュ
```

#### 統合判定ロジック (integrator.py)

カメラ(4状態) x PC(3状態) = 12パターンを網羅:

| カメラ判定 | PC利用状況 | 最終判定       | 理由                                                     |
| ---------- | ---------- | -------------- | -------------------------------------------------------- |
| focused    | focused    | **focused**    | 両方一致、高確信                                         |
| focused    | distracted | **focused**    | カメラが正面を見ている=集中、アプリ切替は作業の一部      |
| focused    | idle       | **idle**       | PC操作停止は確実な情報、カメラの前にいるが操作していない |
| drowsy     | focused    | **drowsy**     | 身体状態はPCでは取れない、カメラが支配                   |
| drowsy     | distracted | **drowsy**     | 身体状態が優先                                           |
| drowsy     | idle       | **drowsy**     | 身体状態が優先                                           |
| distracted | focused    | **focused**    | タイピング中の一時的なよそ見と判断                       |
| distracted | distracted | **distracted** | 両方一致、高確信                                         |
| distracted | idle       | **distracted** | 在席だが操作せず画面外を見ている                         |
| away       | focused    | **away**       | 顔未検出は確実な情報                                     |
| away       | distracted | **away**       | 顔未検出が支配                                           |
| away       | idle       | **away**       | 顔未検出が支配                                           |

#### 通知エンジン (notification/engine.py)

要件定義書の3種通知:

| 種別       | トリガー条件                          | クールダウン |
| ---------- | ------------------------------------- | ------------ |
| drowsy     | 最終判定drowsy連続120秒               | 15分         |
| distracted | 最終判定distracted連続120秒           | 20分         |
| over_focus | 直近90分内で最終判定focusedが80分以上 | 30分         |

通知上限: 設定で1日最大N回（デフォルト6回）

#### 履歴ストア (history/store.py)

SQLite (`~/.local-sidekick/history.db`):

```sql
CREATE TABLE state_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp REAL NOT NULL,
  camera_state TEXT,        -- focused/drowsy/distracted/away
  pc_state TEXT,            -- focused/distracted/idle
  integrated_state TEXT NOT NULL,  -- 最終判定
  confidence REAL,
  source TEXT,              -- rule/llm
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp REAL NOT NULL,
  type TEXT NOT NULL,       -- drowsy/distracted/over_focus
  message TEXT,
  user_action TEXT,         -- accepted/snoozed/dismissed
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE daily_summary (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL UNIQUE,
  total_focused_minutes REAL,
  total_drowsy_minutes REAL,
  total_distracted_minutes REAL,
  total_away_minutes REAL,
  total_idle_minutes REAL,
  notification_count INTEGER,
  notification_accepted INTEGER,
  report_text TEXT,          -- Vertex AI生成レポート
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 Electron App (client/)

#### 技術スタック

- Electron 34+
- React 19 + TypeScript
- Vite (ビルド)
- TailwindCSS
- electron-builder (配布)

#### Main Process (electron/main.ts)

1. **起動時**: Python Engineを子プロセスとしてspawn
2. **メニューバー**: Trayアイコンで常駐（現在の状態に応じてアイコン色変化）
3. **通知**: Python Engineからの通知イベントを受けてmacOS通知を表示
4. **ウィンドウ**: トレイクリックでダッシュボードウィンドウ表示/非表示

#### Python Bridge (electron/python-bridge.ts)

```typescript
// Python Engineの起動・停止・ヘルスチェック
class PythonBridge {
  spawn(): void; // python -m engine.main を起動
  stop(): void; // SIGTERM → graceful shutdown
  healthCheck(): boolean; // GET /api/health
  getPort(): number; // 18080
}
```

#### ダッシュボード画面 (Dashboard.tsx)

- 現在の状態（大きなアイコン+テキスト: Focused / Drowsy / Distracted / Away / Idle）
- 信頼度バー
- 今日の集中時間 / 溶け時間のサマリー
- 直近の通知履歴

#### タイムライン画面 (Timeline.tsx)

- 横軸: 時間（稼働時間帯）
- カラーバー: 状態ごとに色分け（緑=focused, 黄=distracted, 赤=drowsy, 灰=away/idle）
- 通知発火ポイントをマーカー表示

#### 日次レポート画面 (Report.tsx)

- Vertex AI (Gemini) で生成されたレポート表示
- 集中ブロック時間帯
- 溶け時間推定
- 明日の「一手」提案

#### 設定画面 (Settings.tsx)

- 稼働時間（開始/終了）
- 通知上限（回/日）
- カメラON/OFF
- サーバ同期ON/OFF
- アカウント連携

### 3.3 Cloud Run API (server/)

#### エンドポイント

```
POST /api/auth/register       # ユーザー登録
POST /api/auth/login          # ログイン（JWT発行）
GET  /api/settings            # 設定取得
PUT  /api/settings            # 設定更新
POST /api/statistics          # 日次統計アップロード
POST /api/reports/generate    # 日次レポート生成（Vertex AI）
GET  /api/reports/{date}      # レポート取得
GET  /api/health              # ヘルスチェック
```

#### Vertex AI 連携 (services/vertex_ai.py)

日次統計データを入力として、Geminiで自然言語レポートを生成。

入力（統計データのみ、映像・入力内容は送らない）:

```json
{
  "date": "2026-02-11",
  "focused_minutes": 240,
  "drowsy_minutes": 30,
  "distracted_minutes": 45,
  "away_minutes": 60,
  "idle_minutes": 25,
  "notifications": [
    { "type": "drowsy", "time": "14:30", "action": "accepted" },
    { "type": "distracted", "time": "16:00", "action": "snoozed" }
  ],
  "focus_blocks": [
    { "start": "09:00", "end": "11:30", "duration_min": 150 },
    { "start": "13:00", "end": "14:30", "duration_min": 90 }
  ],
  "top_apps": ["Code", "iTerm2", "Brave Browser"]
}
```

出力:

```json
{
  "summary": "今日は合計5.5時間の作業中、4時間（73%）集中できました。...",
  "highlights": ["午前中の2.5時間連続集中が効果的でした"],
  "concerns": ["14:30頃に眠気が来ています。昼食後の時間帯です"],
  "tomorrow_tip": "明日は14:00頃に5分の散歩を入れてみましょう"
}
```

#### Firestore データモデル

```
users/{userId}
  - email: string
  - created_at: timestamp

users/{userId}/settings
  - working_hours_start: "09:00"
  - working_hours_end: "19:00"
  - max_notifications_per_day: 6
  - camera_enabled: true
  - sync_enabled: true

users/{userId}/daily_stats/{date}
  - focused_minutes: number
  - drowsy_minutes: number
  - distracted_minutes: number
  - away_minutes: number
  - idle_minutes: number
  - notification_count: number
  - report: map (Vertex AI生成結果)
```

---

## 4. データフロー

### 4.1 リアルタイム状態推定フロー

```
Camera (200ms) → MediaPipe → Features → [5秒間隔]
  → Rule Classifier (95%: 0ms) or LLM (5%: ~500ms)
  → Camera State

PC Monitor (2s poll) → Snapshot → [30秒間隔]
  → Rule Classifier or LLM
  → PC State

Camera State + PC State → Integrator → Final State
  → WebSocket → Electron UI
  → SQLite History
  → Notification Engine → macOS Notification
```

### 4.2 日次レポート生成フロー

```
稼働時間終了 or ユーザー操作
  → SQLite集計 (state_log → daily_summary)
  → Cloud Run API (POST /api/reports/generate)
  → Vertex AI (Gemini) でレポート生成
  → Firestore保存 + ローカルSQLite保存
  → Electron UIに表示
```

---

## 5. PoC → MVP コード移行マップ

| PoCファイル                                      | MVPファイル                                   | 変更内容                  |
| ------------------------------------------------ | --------------------------------------------- | ------------------------- |
| `poc/shared/camera.py`                           | `engine/engine/camera/capture.py`             | ほぼそのまま              |
| `poc/shared/features.py`                         | `engine/engine/camera/features.py`            | ほぼそのまま              |
| `poc/shared/rule_classifier.py`                  | `engine/engine/estimation/rule_classifier.py` | ほぼそのまま              |
| `poc/shared/prompts.py`                          | `engine/engine/estimation/prompts.py`         | ほぼそのまま              |
| `poc/experiment3_pcusage/monitor.py`             | `engine/engine/pcusage/monitor.py`            | ほぼそのまま              |
| `poc/experiment1_embedded/run_text_llama_cpp.py` | `engine/engine/estimation/llm_backend.py`     | LLM部分を抽出・リファクタ |
| `poc/shared/model_config.py`                     | `engine/engine/config.py`                     | 設定管理に統合            |
| (新規)                                           | `engine/engine/estimation/integrator.py`      | 統合判定ロジック          |
| (新規)                                           | `engine/engine/notification/engine.py`        | 通知エンジン              |
| (新規)                                           | `engine/engine/history/store.py`              | SQLite履歴                |
| (新規)                                           | `engine/engine/api/routes.py`                 | REST API                  |
| (新規)                                           | `engine/engine/api/websocket.py`              | WebSocket                 |

---

## 6. 開発計画（4-5日 x 2-3人）

### 担当分担

- **Person A**: Python Engine（PoC移行 + 新機能）
- **Person B**: Electron App（UI + 統合）
- **Person C**: Cloud Run + Vertex AI + インフラ

### Day 1: 基盤構築

| 担当 | タスク                                                                          |
| ---- | ------------------------------------------------------------------------------- |
| A    | engine/ プロジェクトセットアップ、PoC→engine コード移行、FastAPI基本構造        |
| B    | client/ Electron+React+Vite プロジェクトセットアップ、Tray/メニューバー基本動作 |
| C    | server/ Cloud Run プロジェクトセットアップ、Dockerfile、Firestore設定、認証基盤 |

### Day 2: コア機能

| 担当 | タスク                                                         |
| ---- | -------------------------------------------------------------- |
| A    | 統合判定エンジン(integrator.py)、WebSocket配信、SQLite履歴保存 |
| B    | Dashboard画面、WebSocket接続、Python Bridge（子プロセス管理）  |
| C    | Vertex AI (Gemini) 連携、レポート生成API、Cloud Runデプロイ    |

### Day 3: 機能完成

| 担当 | タスク                                                |
| ---- | ----------------------------------------------------- |
| A    | 通知エンジン、日次集計ロジック、設定API               |
| B    | Timeline画面、Report画面、Settings画面、macOS通知連携 |
| C    | 設定同期API、統計受信API、Firestoreデータモデル実装   |

### Day 4: 統合・テスト

| 担当 | タスク                                                      |
| ---- | ----------------------------------------------------------- |
| A+B  | Electron <-> Python Engine 結合テスト、通知E2Eテスト        |
| C    | Cloud Run <-> ローカル結合テスト、Vertex AIレポート品質確認 |
| 全員 | バグ修正、エッジケース対応                                  |

### Day 5: 仕上げ・提出

| 担当 | タスク                                        |
| ---- | --------------------------------------------- |
| A    | README整備、セットアップ手順                  |
| B    | UI磨き込み、electron-builder でパッケージング |
| C    | Zenn記事執筆、デモ動画準備                    |

---

## 7. 技術スタック一覧

| レイヤー          | 技術                          | バージョン     |
| ----------------- | ----------------------------- | -------------- |
| **Electron**      | Electron                      | 34+            |
| **UI**            | React + TypeScript            | 19             |
| **ビルド**        | Vite + electron-vite          | latest         |
| **CSS**           | TailwindCSS                   | 4              |
| **Python Engine** | Python + FastAPI              | 3.12 / 0.115+  |
| **カメラ**        | OpenCV + MediaPipe            | 4.9+ / 0.10+   |
| **On-device LLM** | llama-cpp-python + Qwen2.5-3B | 0.3+           |
| **PC監視**        | pynput + pyobjc               | 1.7+ / 10+     |
| **ローカルDB**    | SQLite (aiosqlite)            | 標準ライブラリ |
| **Cloud Run**     | Python + FastAPI              | 3.12           |
| **DB**            | Firestore                     | -              |
| **AI**            | Vertex AI (Gemini 2.0 Flash)  | -              |
| **認証**          | Firebase Auth / JWT           | -              |
| **配布**          | electron-builder              | latest         |

---

## 8. MVP スコープ（やること/やらないこと）

### やること (Must)

- [ ] メニューバー常駐 Electron アプリ
- [ ] カメラ → 特徴量 → 状態推定（PoC流用）
- [ ] PC利用状況モニタリング（PoC流用）
- [ ] カメラ + PC 統合判定
- [ ] 通知3種（眠気/散漫/過集中）
- [ ] リアルタイムダッシュボード
- [ ] 今日のタイムライン表示
- [ ] SQLite履歴保存
- [ ] Cloud Run API（認証 + 設定同期）
- [ ] Vertex AI (Gemini) 日次レポート生成
- [ ] 設定画面

### やらないこと (Won't)

- 映像のクラウド保存
- 画面キャプチャ解析
- キー入力内容取得
- SSO / 企業向け機能
- 自動アプリブロック
- Windows/Linux対応
- App Store配布
- 週次/月次レポート
- プライバシー設定UI（MVP後）

---

## 9. 検証方法

### ローカル動作確認

```bash
# 1. Python Engine起動
cd engine && python -m engine.main

# 2. Electron起動（別ターミナル）
cd client && npm run dev

# 3. 手動シナリオテスト
# - 集中→focused表示確認
# - 目を閉じる→drowsy通知確認
# - よそ見→distracted通知確認
# - 離席→away表示確認
# - 90分作業→over_focus通知確認
```

### Cloud Run動作確認

```bash
# 1. ローカルテスト
cd server && uvicorn server.main:app --reload

# 2. Cloud Runデプロイ
gcloud run deploy local-sidekick-api --source .

# 3. APIテスト
curl -X POST $CLOUD_RUN_URL/api/reports/generate \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"date":"2026-02-11", "focused_minutes": 240, ...}'
```

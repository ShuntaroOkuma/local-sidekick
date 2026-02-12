# Local Sidekick

常時カメラ観測+PC利用状況から眠気・集中・散漫を自動推定し、必要なときだけ介入して「1日が無駄に溶ける」を減らすmacOS常駐アプリ。

## アーキテクチャ

```
macOS Electron アプリ
  ├── Main Process (トレイ, 通知, Python Bridge)
  ├── Renderer (React: Dashboard, Timeline, Report, Settings)
  └── Python Engine (FastAPI @ localhost:18080)
        ├── カメラパイプライン (MediaPipe 顔ランドマーク)
        ├── PC利用状況モニター (pynput + pyobjc)
        ├── ルール分類器 (95%) + LLMフォールバック (5%)
        ├── 状態統合 (カメラ + PC → 最終判定)
        ├── 通知エンジン (眠気 / 散漫 / 過集中)
        └── 履歴ストア (SQLite)

Google Cloud
  ├── Cloud Run API (FastAPI, JWT認証)
  ├── Vertex AI Gemini 2.5 Flash (日次レポート生成)
  └── Firestore (ユーザー設定, 統計, レポート)
```

## ディレクトリ構成

```
local-sidekick/
├── client/                   # Electron + React アプリ
│   ├── electron/             # Main Process (tray, preload, python-bridge, notification)
│   ├── src/                  # React Renderer
│   │   ├── pages/            # Dashboard, Timeline, Report, Settings
│   │   ├── components/       # StateIndicator, TimelineChart 等
│   │   ├── hooks/            # useEngineState, useSettings
│   │   └── lib/              # APIクライアント, 型定義
│   └── package.json
├── engine/                   # Python ローカルバックエンド
│   ├── engine/
│   │   ├── api/              # REST API + WebSocket
│   │   ├── camera/           # カメラキャプチャ + 特徴量抽出
│   │   ├── estimation/       # ルール分類, LLM, 統合判定
│   │   ├── pcusage/          # OS操作モニタリング
│   │   ├── notification/     # 通知トリガーロジック (3種)
│   │   ├── history/          # SQLite履歴 + 日次集計
│   │   ├── main.py           # FastAPI エントリポイント
│   │   └── config.py         # 設定管理
│   └── pyproject.toml
├── server/                   # Cloud Run API
│   ├── server/
│   │   ├── api/              # settings, statistics, reports
│   │   ├── services/         # vertex_ai, firestore_client
│   │   ├── models/           # Pydantic スキーマ
│   │   ├── auth.py           # JWT認証
│   │   ├── deps.py           # Firestore共有シングルトン
│   │   └── main.py           # FastAPI エントリポイント
│   ├── Dockerfile
│   └── pyproject.toml
├── poc/                      # 概念実証（参照用、変更しない）
├── docs/
│   ├── architecture.md       # MVP設計書
│   ├── requirements.md       # 企画・仕様
│   ├── manual-testing.md     # 動作確認手順
│   └── poc-plan.md           # PoC実験計画
└── README.md
```

## クイックスタート

### 前提条件

- Apple Silicon搭載macOS（M3/M4, 16GB以上のRAM）
- Python 3.12以上
- Node.js 20以上

### 1. Engine

```bash
cd engine
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# （任意）カメラ・LLM用モデルをダウンロード
python models/download.py

python -m engine.main
# → http://localhost:18080
```

### 2. Client

```bash
cd client
npm install
npm run dev
# → Electronアプリがトレイアイコン付きで起動
```

### 3. Server（クラウド同期用、任意）

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

USE_MEMORY_STORE=true JWT_SECRET=dev-secret uvicorn server.main:app --port 8081
# → http://localhost:8081
```

### 3a. Server Docker起動（結合テスト推奨）

Cloud Runと同じDockerイメージ + Firestore Emulatorで本番に近い環境をローカルで再現します。

```bash
cd server
docker compose up --build
# → API: http://localhost:8080
# → Firestore Emulator: http://localhost:8086
```

Vertex AIはデフォルトでダミーレスポンスを返します。実際のVertex AIを使う場合:

```bash
gcloud auth application-default login
GCP_PROJECT_ID=your-project docker compose -f docker-compose.yml -f docker-compose.vertex.yml up --build
```

停止・クリーンアップ:

```bash
docker compose down
```

### macOS権限設定

- **カメラ**: カメラによる状態推定に必要
- **入力監視**（システム設定 > プライバシーとセキュリティ > 入力監視）: キーボード/マウスイベント計測に必要
- **アクセシビリティ**（システム設定 > プライバシーとセキュリティ > アクセシビリティ）: アイドル時間検出に必要

## 主要機能

| 機能                 | 説明                                                                           |
| -------------------- | ------------------------------------------------------------------------------ |
| リアルタイム状態推定 | カメラ（顔ランドマーク）+ PC利用 → focused / drowsy / distracted / away / idle |
| 通知3種              | 眠気（120秒連続）、散漫（120秒連続）、過集中（90分中80分集中）                 |
| ダッシュボード       | リアルタイム状態表示、信頼度バー、今日のサマリー                               |
| タイムライン         | 時間ごとの状態を色分け表示                                                     |
| 日次レポート         | Vertex AI (Gemini 2.5 Flash) によるAIレポート生成                              |
| 設定同期             | Cloud Run API + JWT認証 + Firestore                                            |
| プライバシー重視     | 映像はすべてオンデバイス処理、統計のみサーバーに送信                           |

## 技術スタック

| レイヤー        | 技術                                          |
| --------------- | --------------------------------------------- |
| デスクトップ    | Electron 34 + React 19 + TypeScript           |
| ビルド          | electron-vite + Vite 6 + TailwindCSS 4        |
| Engine          | Python 3.12 + FastAPI + aiosqlite             |
| カメラ          | OpenCV + MediaPipe Face Landmarks             |
| オンデバイスLLM | llama-cpp-python + Qwen2.5-3B (Q4_K_M, Metal) |
| PC監視          | pynput + pyobjc                               |
| クラウドAPI     | Cloud Run + FastAPI                           |
| AI              | Vertex AI (Gemini 2.5 Flash)                  |
| データベース    | Firestore（クラウド）+ SQLite（ローカル）     |
| 認証            | JWT (python-jose + passlib)                   |

## プライバシー設計

- 映像は端末外へ出さない（デフォルト）
- キー入力内容は一切記録しない（イベント数のみ）
- スクリーンキャプチャなし
- サーバーへ送るのは集計統計のみ
- カメラは設定画面でOFFにできる

## ドキュメント

- [企画・仕様書](docs/requirements.md)
- [MVP設計書](docs/architecture.md)
- [動作確認手順](docs/manual-testing.md)
- [PoC実験計画](docs/poc-plan.md)

## ライセンス

Private - Google Cloud Japan AI Hackathon Vol.4

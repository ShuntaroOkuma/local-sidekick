# Local Sidekick

常時カメラ観測+PC利用状況から眠気・集中・散漫を自動推定し、必要なときだけ介入して「1日が無駄に溶ける」を減らすmacOS常駐アプリ。

## アーキテクチャ

```
macOS Electron アプリ
  ├── Main Process (トレイ, 通知, Python Bridge)
  ├── Renderer (React: Dashboard, Timeline, Report, Settings)
  ├── Avatar Overlay (透明BrowserWindow, CSSキャラクター)
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
│   ├── electron/             # Main Process (tray, preload, python-bridge, notification, avatar-window)
│   ├── src/                  # React Renderer
│   │   ├── pages/            # Dashboard, Timeline, Report, Settings
│   │   ├── components/       # StateIndicator, TimelineChart 等
│   │   ├── hooks/            # useEngineState, useSettings
│   │   ├── avatar/           # アバターオーバーレイ (キャラクター, ステートマシン, アニメーション)
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
├── tools/                    # 開発・テストユーティリティ
│   └── mock_engine.py        # アバターテスト用モックEngine (WebSocket + REST)
├── poc/                      # 概念実証（参照用、変更しない）
├── docs/
│   ├── architecture.md       # MVP設計書
│   └── manual-testing.md     # 動作確認手順
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
| デスクトップアバター | 常に最前面に表示されるアニメキャラクターがリアルタイムで状態に反応             |
| プライバシー重視     | 映像はすべてオンデバイス処理、統計のみサーバーに送信                           |

## アバターオーバーレイ

デスクトップに常駐する小さなアニメキャラクターが、あなたの状態にリアルタイムで反応します。

### 仕組み

- メインアプリとは別の透明な常時最前面 `BrowserWindow` で動作
- Engine WebSocket (`/ws/state`) に直接接続し、状態・通知をリアルタイム取得
- デバウンス付きステートマシンでEngine状態をアバターアニメーションに変換

### アバターモード

| Engine状態   | アバターモード | 動作                                         |
| ------------ | -------------- | -------------------------------------------- |
| focused      | hidden         | キャラクターが退避して非表示（集中中）       |
| idle         | peek           | 横からひょっこり覗く                         |
| drowsy       | dozing         | ゆっくり呼吸アニメーション + ZZZエフェクト   |
| distracted   | wake-up        | バウンスして注意を引く                       |
| away         | peek           | 覗いて戻りを待つ                             |

Engineからの通知（眠気・散漫・過集中）は、アバターが有効な間はOS通知の代わりにキャラクター上の吹き出しとして表示されます。

### 設定

アバターは **設定 > アバター** からON/OFFを切り替えられます。OFFにするとアバターウィンドウが非表示になり、OS標準通知にフォールバックします。

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
- アバターは設定画面でOFFにできる

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

## ドキュメント

- [MVP設計書](docs/architecture.md)
- [動作確認手順](docs/manual-testing.md)

## ライセンス

MIT License. 詳細は [LICENSE](LICENSE) ファイルを参照してください。

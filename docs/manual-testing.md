# Local Sidekick MVP - 動作確認手順

## 前提条件

- macOS
- Python 3.12+
- Node.js 20+
- (オプション) Google Cloud SDKがインストール済み（サーバーのFirestore/Vertex AI連携確認時）

## 1. Engine (Python ローカルバックエンド)

### 1.1 セットアップ

```bash
cd engine
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

**モデルファイルが必要な場合（カメラ・LLM機能）:**

```bash
# MediaPipe モデル（カメラ機能用）
python -c "import mediapipe as mp; mp.solutions.face_mesh.FaceMesh()"

# GGUF モデル（LLMフォールバック用）
# models/ ディレクトリに Qwen2.5-3B-Instruct-Q4_K_M.gguf を配置
```

### 1.2 起動

```bash
source .venv/bin/activate
python -m engine.main
```

起動ログに以下が表示されること:
```
INFO: Engine started on http://localhost:18080
```

### 1.3 REST API テスト

```bash
# ヘルスチェック
curl -s http://localhost:18080/api/health | python3 -m json.tool
# 期待: {"status": "ok"}

# 現在の状態取得
curl -s http://localhost:18080/api/state | python3 -m json.tool
# 期待: state, confidence, camera_state, pc_state, timestamp を含むJSON

# 設定取得
curl -s http://localhost:18080/api/settings | python3 -m json.tool
# 期待: working_hours_start, working_hours_end, distracted_cooldown_minutes(=20) 等

# 設定更新
curl -s -X PUT http://localhost:18080/api/settings \
  -H "Content-Type: application/json" \
  -d '{"max_notifications_per_day": 10}' | python3 -m json.tool
# 期待: max_notifications_per_day が 10 に更新

# 履歴取得
curl -s http://localhost:18080/api/history | python3 -m json.tool
# 期待: state_log 配列（起動直後は少量）

# 日次統計
curl -s http://localhost:18080/api/daily-stats | python3 -m json.tool
# 期待: focused_minutes, drowsy_minutes 等（unprefixed keys）

# 通知一覧
curl -s http://localhost:18080/api/notifications | python3 -m json.tool
# 期待: 空配列（通知未発生の場合）

# 未応答通知
curl -s http://localhost:18080/api/notifications/pending | python3 -m json.tool
# 期待: 空配列

# エンジン停止
curl -s -X POST http://localhost:18080/api/engine/stop | python3 -m json.tool
# 期待: {"status": "stopped"}

# エンジン再起動
curl -s -X POST http://localhost:18080/api/engine/start | python3 -m json.tool
# 期待: {"status": "started"}

# レポート生成（ダミー）
curl -s -X POST http://localhost:18080/api/reports/generate | python3 -m json.tool
# 期待: 日次統計 + report フィールド
```

### 1.4 WebSocket テスト

```bash
# websocat が必要: brew install websocat
websocat ws://localhost:18080/ws/state
# 期待: {"type": "state_update", "state": "...", ...} が定期的に流れる
```

### 1.5 確認ポイント

| 項目 | 期待動作 | カメラなし時 |
|------|---------|------------|
| PC状態監視 | アプリ名・キー入力をモニター | 正常動作 |
| カメラ状態推定 | MediaPipeで顔特徴量→状態判定 | away固定（graceful degradation） |
| 統合判定 | カメラ+PC→最終状態 | PC状態のみで判定 |
| LLMフォールバック | ルール分類で低信頼度時にLLM使用 | ルールのみ（LLMスキップ） |
| 履歴保存 | SQLite (~/.local-sidekick/history.db) | 正常保存 |

---

## 2. Client (Electron アプリ)

### 2.1 セットアップ

```bash
cd client
npm install
```

### 2.2 ビルド確認

```bash
# TypeScript型チェック
npx tsc --noEmit
# 期待: エラーなし

# プロダクションビルド
npm run build
# 期待: dist-electron/main.js, dist-electron/preload.js, dist/ が生成
```

### 2.3 開発サーバー起動

```bash
# Engine が localhost:18080 で起動していること
npm run dev
```

起動ログ:
```
dev server running for the electron renderer process at: http://localhost:5173/
start electron app...
```

### 2.4 UI確認ポイント

| 画面 | 確認内容 |
|------|---------|
| メニューバー | トレイアイコン表示、左クリックでウィンドウ表示/非表示 |
| Dashboard | 現在の状態（アイコン+テキスト）、信頼度、今日の集中時間 |
| Timeline | 時系列カラーバー（緑=focused, 黄=distracted, 赤=drowsy, 灰=away/idle） |
| Report | 日次レポート表示（Vertex AI未接続時はダミー） |
| Settings | 稼働時間、通知上限、カメラON/OFF、サーバ同期ON/OFF |
| 右クリックメニュー | Dashboard / Settings / Quit Local Sidekick |

### 2.5 PythonBridge

- Engine が未起動の場合: `Failed to start Python Engine` ログが出るが、アプリは起動する
- Engine が起動済みの場合: 自動接続してリアルタイム状態表示

---

## 3. Server (Cloud Run API)

### 3.1 セットアップ

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3.2 ローカル起動

```bash
# GCPプロジェクト未設定時はインメモリストアを使用
USE_MEMORY_STORE=true JWT_SECRET=test-secret uvicorn server.main:app --port 8081
```

### 3.3 API テスト

```bash
BASE=http://localhost:8081

# 1. ヘルスチェック
curl -s $BASE/api/health | python3 -m json.tool
# 期待: {"status": "ok", "service": "local-sidekick-api"}

# 2. ユーザー登録
curl -s -X POST $BASE/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}' | python3 -m json.tool
# 期待: {"access_token": "eyJ...", "token_type": "bearer"}

# 3. ログイン
TOKEN=$(curl -s -X POST $BASE/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Token: ${TOKEN:0:30}..."
# 期待: JWT トークン取得

# 4. 設定取得
curl -s $BASE/api/settings/ \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# 期待: デフォルト設定（working_hours_start: "09:00" 等）

# 5. 設定更新
curl -s -X PUT $BASE/api/settings/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"camera_enabled":false}' | python3 -m json.tool
# 期待: camera_enabled が false に更新

# 6. 統計アップロード
curl -s -X POST $BASE/api/statistics/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-02-11","focused_minutes":240,"drowsy_minutes":30,"distracted_minutes":45,"away_minutes":60,"idle_minutes":25,"notification_count":3}' \
  | python3 -m json.tool
# 期待: {"status": "ok", "date": "2026-02-11"}

# 7. レポート生成
curl -s -X POST $BASE/api/reports/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-02-11","focused_minutes":240,"drowsy_minutes":30,"distracted_minutes":45,"away_minutes":60,"idle_minutes":25,"notification_count":3}' \
  | python3 -m json.tool
# 期待: summary, highlights, concerns, tomorrow_tip を含むJSON
# (Vertex AI未接続時はダミーレポート)

# 8. レポート取得
curl -s $BASE/api/reports/2026-02-11 \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# 期待: 手順7で生成したレポートと同内容
```

### 3.4 エラーケース確認

```bash
# 重複登録 → 409
curl -s -X POST $BASE/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}' | python3 -m json.tool
# 期待: {"detail": "User with this email already exists"}

# パスワード不一致 → 401
curl -s -X POST $BASE/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"wrong"}' | python3 -m json.tool
# 期待: {"detail": "Invalid email or password"}

# 認証なしアクセス → 403
curl -s $BASE/api/settings/ | python3 -m json.tool
# 期待: {"detail": "Not authenticated"}
```

### 3.5 注意事項

- **URL末尾スラッシュ**: `/api/settings/`, `/api/statistics/` はスラッシュ付きが正式（スラッシュなしは307リダイレクト）
- **USE_MEMORY_STORE**: GCPプロジェクト未設定時は `USE_MEMORY_STORE=true` を付けて起動（サーバー再起動でデータは消える）
- **Vertex AI**: GCPプロジェクト未設定時はダミーレポートが返る

---

## 4. 結合テスト（Engine + Client）

### 4.1 手順

1. Engine起動: `cd engine && source .venv/bin/activate && python -m engine.main`
2. Client起動: `cd client && npm run dev`
3. メニューバーのトレイアイコンをクリックしてDashboard表示
4. Dashboardに現在の状態がリアルタイム表示されることを確認

### 4.2 シナリオテスト

| シナリオ | 操作 | 期待結果 |
|---------|------|---------|
| 集中状態 | PCで作業を続ける | Dashboard: focused表示 |
| 離席 | PCから離れる（カメラON時） | Dashboard: away表示 |
| アイドル | 数分間操作なし | Dashboard: idle表示 |
| 通知確認 | 通知一覧で確認 | 通知履歴表示 |
| 設定変更 | Settings画面で設定変更 | 即時反映 |

---

## 5. 自動テスト結果サマリー (2026-02-11)

### Engine
| テスト | 結果 |
|-------|------|
| GET /api/health | ✅ OK |
| GET /api/state | ✅ state=idle (PC監視のみ) |
| GET /api/settings | ✅ distracted_cooldown=20 |
| PUT /api/settings | ✅ 設定更新反映 |
| GET /api/history | ✅ state_log配列返却 |
| GET /api/daily-stats | ✅ unprefixed keys |
| GET /api/notifications | ✅ 空配列 |
| GET /api/notifications/pending | ✅ 空配列 |
| POST /api/engine/stop | ✅ 監視停止 |
| POST /api/engine/start | ✅ 監視再開 |
| POST /api/reports/generate | ✅ 統計+レポート |
| WebSocket /ws/state | ✅ type=state_update |

### Client
| テスト | 結果 |
|-------|------|
| npm install | ✅ 成功 |
| npm run build | ✅ 成功 |
| npx tsc --noEmit | ✅ 型エラーなし |
| Electron起動 | ✅ Tray + Renderer |
| PythonBridge | ✅ Engine未起動時graceful failure |

### Server
| テスト | 結果 |
|-------|------|
| GET /api/health | ✅ OK |
| POST /api/auth/register | ✅ JWT返却 |
| POST /api/auth/login | ✅ JWT返却 |
| GET /api/settings/ | ✅ デフォルト設定 |
| PUT /api/settings/ | ✅ 設定更新 |
| POST /api/statistics/ | ✅ 統計保存 |
| POST /api/reports/generate | ✅ ダミーレポート |
| GET /api/reports/{date} | ✅ レポート取得 |
| 重複登録 | ✅ 409 |
| パスワード不一致 | ✅ 401 |
| 認証なし | ✅ 403 |

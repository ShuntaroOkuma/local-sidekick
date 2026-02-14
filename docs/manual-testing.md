# Local Sidekick - 手動テスト手順

> 誰でも再現できるよう、基本的にGUI操作で確認します。
> アバターなど再現が難しい項目はCLI（curl）で効率的に確認します。

---

## 前提条件

- macOS
- Python 3.12+（`python3 --version` で確認）
- Node.js 20+（`node --version` で確認）

---

## 0. セットアップ（初回のみ）

### Engine

```bash
cd engine
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[llama,download]"
```

### Client

```bash
cd client
npm install
```

### モデルダウンロード（GUIでも可能、後述）

```bash
cd engine && source .venv/bin/activate
python models/download.py
# face_landmarker (3.6MB) + qwen2.5-3b (2.0GB) がダウンロードされる
```

---

## 1. 起動

2つのターミナルを開きます。

**ターミナル1: Engine**

```bash
cd engine && source .venv/bin/activate && python -m engine.main
```

ログに `Uvicorn running on http://127.0.0.1:18080` が出れば OK。

**ターミナル2: Client（Electronアプリ）**

```bash
cd client && npm run dev
```

Electronウィンドウが自動で開きます。

---

## 2. Dashboard（メイン画面）

アプリが開くと Dashboard が表示されます。

### 確認項目

| # | 確認内容 | 期待動作 |
|---|---------|---------|
| 1 | 接続状態 | 左上に緑色のドット（Engine接続済み） |
| 2 | 状態表示 | 中央の円形インジケーターに現在の状態（focused / drowsy / distracted / away）と信頼度（%）が表示される |
| 3 | サブ状態 | インジケーター下に Camera State / PC State が表示される（統合推定後はnull表示も正常） |
| 4 | 今日のサマリー | 集中・眠気・散漫の各分数が表示される |
| 5 | 最近の通知 | 通知が発生していれば一覧表示される |
| 6 | リアルタイム更新 | PCで作業していると状態が変化する（30秒ごとに自動更新） |

### テスト操作

1. **集中状態の確認**: PCで普通に作業（コードを書く等）→ Dashboard に `focused` と表示される
2. **離席の確認**: カメラONの状態でPCから離れる → `away` に変化する
3. **Engine停止時の確認**: Engine を Ctrl+C で停止 → 接続ドットが赤に変わる

---

## 3. Timeline（タイムライン）

画面下部のナビゲーションで **Timeline** タブをタップします。

### 確認項目

| # | 確認内容 | 期待動作 |
|---|---------|---------|
| 1 | 日付ナビゲーション | 左右矢印で前日/翌日に移動できる。未来日には進めない |
| 2 | タイムライン表示 | 終日のカラーバーが表示される（緑=focused, 黄=distracted, 赤=drowsy, 灰=away） |
| 3 | 通知ログ | その日の通知が時刻・種類・メッセージとともに一覧表示される |
| 4 | データなし | 過去日で記録がなければ「No data yet」と表示される |

### テスト操作

1. 今日の日付で表示 → Engine起動中にカラーバーが伸びていくことを確認
2. 左矢印で前日に移動 → データがなければ空表示

---

## 4. Report（日次レポート）

画面下部のナビゲーションで **Report** タブをタップします。

### 確認項目

| # | 確認内容 | 期待動作 |
|---|---------|---------|
| 1 | レポート未生成時 | 「レポートを生成」ボタンが表示される |
| 2 | レポート生成 | ボタン押下でレポートが生成される（ローディング表示後に結果表示） |
| 3 | レポート内容 | サマリー・ハイライト（緑）・気になるポイント（黄）・明日の一手 が表示される |

### テスト操作

1. 「レポートを生成」ボタンをクリック
2. レポートが表示されることを確認（Vertex AI未接続時はダミーレポート）

---

## 5. Settings（設定）

画面下部のナビゲーションで **Settings** タブをタップします。

### 確認項目

| # | セクション | 確認内容 | 期待動作 |
|---|-----------|---------|---------|
| 1 | アバター | トグルをON/OFF | 即座にアバターウィンドウが表示/非表示される（保存不要） |
| 2 | カメラ | ON/OFFトグル | 保存後にカメラ監視が開始/停止される |
| 3 | サーバ同期 | ON/OFFトグル | ONにするとCloud Run接続セクションが展開される（詳細はセクション12参照） |
| 4 | AIモデル | ティア選択（無効/軽量/推奨） | 選択したモデルティアが保存される |
| 5 | 保存 | 「保存」ボタンをクリック | 「保存しました」メッセージが3秒間表示される |

### モデルダウンロード（GUI操作）

1. Settings → AIモデル設定 を開く
2. 「軽量 (3B)」または「推奨 (7B)」ボタンをクリック
3. モデルカードの「ダウンロード」ボタンをクリック
4. ダウンロード中のプログレス表示を確認
5. ダウンロード完了後、ステータスが「ダウンロード済み」に変わる

| # | 確認内容 | 期待動作 |
|---|---------|---------|
| 1 | ティア「無効」選択 | LLM不使用（ルールベース判定のみ）。モデル不要 |
| 2 | ティア「軽量」選択 + モデル未DL | 警告メッセージが表示される |
| 3 | モデルダウンロード | プログレス表示後に完了 |
| 4 | モデル削除 | 「削除」ボタンで削除、ステータスが「未ダウンロード」に戻る |

---

## 6. メニューバー・トレイ操作

| # | 操作 | 期待動作 |
|---|------|---------|
| 1 | メニューバーのトレイアイコンをクリック | ウィンドウが表示/非表示切り替え |
| 2 | トレイアイコン右クリック | コンテキストメニュー表示（Dashboard / Settings / Quit） |
| 3 | メニューから「Dashboard」選択 | Dashboard画面が開く |
| 4 | メニューから「Settings」選択 | Settings画面が開く |
| 5 | メニューから「Quit Local Sidekick」選択 | アプリが終了する |
| 6 | ウィンドウの閉じるボタン（×） | ウィンドウは非表示になるが、アプリはトレイに残る |

---

## 7. 通知テスト

通知は特定の状態が一定時間継続すると自動発火します。自然発火を待つのは大変なので、**Mock Engine** を使ってテストします。

### Mock Engine での通知テスト

**手順:**

1. 本物のEngineが起動していれば停止する（Ctrl+C）
2. Mock Engine を起動:

```bash
cd engine && source .venv/bin/activate
python ../tools/mock_engine.py
```

3. Clientを起動（別ターミナル）:

```bash
cd client && npm run dev
```

4. 以下のcurlコマンドで通知を発火:

```bash
# 眠気通知
curl -X POST http://localhost:18080/test/notification/drowsy
# → OS通知: 「眠気が来ています！立ちましょう」

# 散漫通知
curl -X POST http://localhost:18080/test/notification/distracted
# → OS通知: 「集中が途切れています」

# 過集中通知
curl -X POST http://localhost:18080/test/notification/over_focus
# → OS通知: 「休憩しませんか？」
```

### 通知チェックリスト

| # | 確認内容 | 期待動作 |
|---|---------|---------|
| 1 | 通知表示 | macOS通知センターにバナー表示される |
| 2 | アクションボタン | 「実行」「あとで」ボタンが表示される |
| 3 | アバターON時 | Settings でアバターをONにすると、OS通知の代わりにアバター上の吹き出しで表示される |

---

## 8. アバター機能テスト

アバターの状態変化は手動では再現が難しいため、**Mock Engine + curl** でテストします。

### 準備

1. Mock Engine 起動:

```bash
cd engine && source .venv/bin/activate
python ../tools/mock_engine.py
```

2. Client 起動（別ターミナル）:

```bash
cd client && npm run dev
```

3. Settings 画面でアバターを **ON** にする

### 状態切り替え

```bash
# focused: アバターが退場して非表示になる
curl -X POST http://localhost:18080/test/state/focused

# drowsy: アバターがうとうと（ZZZ表示）
curl -X POST http://localhost:18080/test/state/drowsy

# distracted: アバターが跳ねて注意喚起
curl -X POST http://localhost:18080/test/state/distracted

# away: アバターが覗き込み
curl -X POST http://localhost:18080/test/state/away
```

### 吹き出し（通知）

```bash
# 眠気通知 → アバター上に吹き出し表示（5秒後に自動消去）
curl -X POST http://localhost:18080/test/notification/drowsy

# 散漫通知
curl -X POST http://localhost:18080/test/notification/distracted

# 過集中通知
curl -X POST http://localhost:18080/test/notification/over_focus
```

### アバター チェックリスト

| # | 項目 | 期待動作 |
|---|------|---------|
| 1 | 初期表示 | 画面右下にキャラクターが表示される |
| 2 | focused → hidden | 退場アニメーション後に非表示 |
| 3 | drowsy → dozing | ゆっくり呼吸 + ZZZ表示 |
| 4 | distracted → wake-up | バウンドアニメーション |
| 5 | 通知 → 吹き出し | メッセージが5秒間表示されて自動消去 |
| 6 | 全画面アプリ上 | VSCode等の全画面上にも表示される |
| 7 | アバターOFF | Settings でトグルOFF → アバター非表示 |
| 8 | アバターON | Settings でトグルON → アバター再表示 |
| 9 | アバターOFF時の通知 | OS通知（macOS通知センター）に切り替わる |

---

## 9. 統合推定のテスト

統合推定（統合ルール + LLM）が正しく動作しているか確認します。

### 9.1 ルール判定の確認（本物のEngine使用）

| シナリオ | 操作 | 期待状態 | 判定方法 |
|---------|------|---------|---------|
| 集中 | カメラに正面を向け、キーボードで入力 | focused | ルール即判定（Rule 3） |
| 離席 | カメラの前から離れる | away | ルール即判定（Rule 1） |

Engineのログで確認:
```
# ルール判定の場合: source="rule" と表示される
# LLM判定の場合: source="llm" と表示される
```

### 9.2 LLM判定の確認

LLMが動作するためにはモデルが必要です。

1. Settings → AIモデル設定 → 「軽量 (3B)」を選択、モデルをダウンロード
2. 保存してEngineを再起動
3. 以下の曖昧なシナリオでLLM判定を確認:

| シナリオ | 操作 | 期待状態 | 備考 |
|---------|------|---------|------|
| 横向き会話 | 横を向いて誰かと話す | focused | LLM: 横向き+操作あり=会話中 |
| MTG中 | Zoomを開いて操作なし | focused | LLM: Zoom+正面=MTG視聴 |

### 9.3 フォールバックの確認

1. Settings → AIモデル設定 → 「無効」を選択して保存
2. Engineを再起動
3. 曖昧なシナリオ（横向き等）→ フォールバック関数で判定される（source="rule"、信頼度低め）

---

## 10. システム連携テスト

| # | シナリオ | 操作 | 期待動作 |
|---|---------|------|---------|
| 1 | スリープ復帰 | MacBookの蓋を閉じて開く | 監視が一時停止→自動再開。古いデータで判定されない |
| 2 | Engine未起動 | Engineを停止した状態でClientを起動 | 接続ドット赤、アプリは正常に動作する |
| 3 | Engine再接続 | Client起動中にEngineを起動 | 自動接続されてリアルタイム表示が始まる |

---

## 11. Server / Cloud Run 連携テスト

> サーバーはオプショナル（ローカルのみでも動作する）。
> Engine → Cloud Run へのプロキシ機能、クラウド認証、フォールバック動作を含めて確認します。

### 11.1 セットアップ

**Server（Cloud Run 相当）をローカルで起動:**

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# メモリストア + テスト用JWTシークレットで起動
USE_MEMORY_STORE=true JWT_SECRET=test-secret uvicorn server.main:app --port 8081
```

**Engine に httpx を含む依存をインストール:**

```bash
cd engine && source .venv/bin/activate
pip install -e ".[llama,download]"
```

**Engine / Client を通常通り起動:**

```bash
# ターミナル1
cd engine && source .venv/bin/activate && python -m engine.main

# ターミナル2
cd client && npm run dev
```

---

### 11.2 Server API 単体確認（CLI）

Server が正しく動作しているかを直接確認します。

```bash
BASE=http://localhost:8081

# ヘルスチェック
curl -s $BASE/api/health | python3 -m json.tool
# 期待: {"status": "ok", "service": "local-sidekick-api"}

# ユーザー登録
curl -s -X POST $BASE/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}' | python3 -m json.tool
# 期待: access_token を含むJSON

# ログイン
TOKEN=$(curl -s -X POST $BASE/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 設定取得
curl -s $BASE/api/settings/ -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# 期待: camera_enabled, sync_enabled 等

# レポート生成（Vertex AI が有効な場合のみ成功）
curl -s -X POST $BASE/api/reports/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-02-13","focused_minutes":240,"drowsy_minutes":30,"distracted_minutes":45,"away_minutes":60,"notification_count":3}' \
  | python3 -m json.tool
# 期待: summary, highlights, concerns, tomorrow_tip を含むJSON
```

---

### 11.3 Settings UI - Cloud Run 接続設定

| # | 操作 | 期待動作 |
|---|------|---------|
| 1 | Settings → サーバ同期を **ON** にする | 「Cloud Run 接続」セクションが展開表示される |
| 2 | Cloud Run URL に `http://localhost:8081` を入力 | URL入力欄に値が表示される |
| 3 | 「保存」をクリック | 「保存しました」メッセージ。cloud_run_url が Engine config に保存される |

**CLI で設定確認:**

```bash
curl -s http://localhost:18080/api/settings | python3 -m json.tool
# 期待: "sync_enabled": true, "cloud_run_url": "http://localhost:8081", "cloud_auth_email": ""
```

---

### 11.4 クラウド認証（新規登録 → ログイン → ログアウト）

#### 新規登録

| # | 操作 | 期待動作 |
|---|------|---------|
| 1 | メールアドレスに `test@example.com` を入力 | - |
| 2 | パスワードに `testpass123` を入力 | - |
| 3 | 「新規登録」ボタンをクリック | ボタンが「処理中...」→ 登録成功後に「test@example.com としてログイン中」表示に切り替わる |

**CLI で確認:**

```bash
curl -s http://localhost:18080/api/settings | python3 -m json.tool
# 期待: "cloud_auth_email": "test@example.com"
```

```bash
# config.json にトークンが保存されていることを確認
cat ~/.local-sidekick/config.json | python3 -m json.tool
# 期待: "cloud_auth_token": "eyJ..." (JWT), "cloud_auth_email": "test@example.com"
```

#### ログアウト

| # | 操作 | 期待動作 |
|---|------|---------|
| 1 | 「ログアウト」ボタンをクリック | 「処理中...」→ メール/パスワード入力欄+ログイン/新規登録ボタンに戻る |

**CLI で確認:**

```bash
curl -s http://localhost:18080/api/settings | python3 -m json.tool
# 期待: "cloud_auth_email": ""
```

#### ログイン（登録済みアカウント）

| # | 操作 | 期待動作 |
|---|------|---------|
| 1 | メール `test@example.com`、パスワード `testpass123` を入力 | - |
| 2 | 「ログイン」ボタンをクリック | 「test@example.com としてログイン中」表示に切り替わる |

#### エラーケース

| # | 操作 | 期待動作 |
|---|------|---------|
| 1 | 間違ったパスワードでログイン | 「ログインに失敗しました」エラー表示 |
| 2 | Server を停止した状態でログイン | 「ログインに失敗しました」エラー表示 |
| 3 | Cloud Run URL を空のままログイン試行（CLI） | 400エラー（`cloud_run_url not configured`） |

**CLI でエラーケース確認:**

```bash
curl -s -X POST http://localhost:18080/api/cloud/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"wrong"}' | python3 -m json.tool
# 期待: {"detail": "Cloud login failed"} (401)
```

---

### 11.5 レポート生成 - Cloud Run プロキシ

**前提:** sync_enabled=ON、Cloud Run URL設定済み、ログイン済みの状態で実施。

#### Cloud レポート（正常系）

| # | 操作 | 期待動作 |
|---|------|---------|
| 1 | Report タブを開く | 「レポートを生成」ボタンが表示される |
| 2 | 「レポートを生成」ボタンをクリック | 「生成中...」→ AI生成レポートが表示される（サマリー、ハイライト、気になるポイント、明日の一手） |
| 3 | フォールバック警告バナー | 表示されない（Cloud Run成功時） |

**CLI で確認:**

```bash
curl -s -X POST "http://localhost:18080/api/reports/generate" | python3 -m json.tool
# 期待: "report_source": "cloud", "report": {"summary": "...", "highlights": [...], ...}
```

> **注意:** Server をローカル起動（`USE_MEMORY_STORE=true`）の場合、Vertex AI が未設定だとレポート生成が500エラーになる可能性があります。
> Vertex AI を使う場合は以下で起動:
> ```bash
> cd server
> GCP_PROJECT_ID=your-project JWT_SECRET=test-secret uvicorn server.main:app --port 8081
> ```

#### フォールバック（Cloud Run 到達不能時）

| # | 操作 | 期待動作 |
|---|------|---------|
| 1 | Server（ポート8081）を **Ctrl+C で停止** する | - |
| 2 | Report タブで「レポートを生成」ボタンをクリック | ローカルダミーレポートが表示される |
| 3 | フォールバック警告バナー | 黄色背景で「Cloud Run に接続できませんでした。ローカルレポートを表示しています。」が表示される |

**CLI で確認:**

```bash
# Server停止状態で実行
curl -s -X POST "http://localhost:18080/api/reports/generate" | python3 -m json.tool
# 期待: "report_source": "local", "report": {"summary": "本日の作業統計: 集中 0分", ...}
```

#### sync_enabled OFF の場合

| # | 操作 | 期待動作 |
|---|------|---------|
| 1 | Settings → サーバ同期を **OFF** にして保存 | - |
| 2 | Report タブで「レポートを生成」をクリック | ローカルダミーレポートが表示される |
| 3 | フォールバック警告バナー | 表示されない（sync_enabled=OFFなのでフォールバックは正常動作） |

---

### 11.6 Cloud 連携チェックリスト

| # | 確認内容 | 期待動作 | 確認方法 |
|---|---------|---------|---------|
| 1 | Server ヘルスチェック | `{"status": "ok"}` が返る | CLI: Server直接 |
| 2 | Cloud Run URL 保存 | config.json に cloud_run_url が保存される | CLI: Engine Settings API |
| 3 | 新規登録 | Cloud Run にアカウント作成、JWT を config に保存 | Settings UI |
| 4 | ログイン | JWT を config に保存、UI にメール表示 | Settings UI |
| 5 | ログアウト | JWT とメールを config からクリア | Settings UI |
| 6 | Cloud レポート生成 | Vertex AI によるAIレポートが返る | Report UI |
| 7 | フォールバック | Cloud Run不通時にローカルダミーレポート+警告バナー | Server停止して確認 |
| 8 | sync OFF | Cloud Run を使わずローカルレポート（警告なし） | Settings でOFF |
| 9 | JWT 期限切れ | 401 → ログインに失敗（再ログインを促す） | JWT期限後にレポート生成 |

---

## 12. 自動テスト

```bash
# Engine のユニットテスト（41テスト）
cd engine && source .venv/bin/activate
python -m pytest engine/tests/ -v
# 期待: 41 passed

# Client のビルド確認
cd client
npx tsc --noEmit   # TypeScript型チェック
npm run build       # プロダクションビルド
```

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| Dashboard が「接続中...」のまま | Engine未起動 | ターミナル1でEngine起動を確認 |
| カメラが動作しない | カメラ権限未付与 | macOS設定 → プライバシーとセキュリティ → カメラ でターミナルに権限を付与 |
| LLMが動作しない | モデル未ダウンロード | Settings → AIモデル設定 でモデルをダウンロード |
| アバターが表示されない | アバターOFF | Settings → アバター でトグルをONにする |
| `pip install` でエラー | llama-cpp-python のビルド失敗 | `CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python` を試す |
| ポート18080が使用中 | 前回のEngineプロセスが残っている | `lsof -i :18080` で確認、`kill <PID>` で停止 |

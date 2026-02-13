# レポート生成機能 - GCP接続計画

## Context

レポート生成ボタンを押すと、現在はエンジン側でハードコードされたダミーレポートが返される。一方、Cloud Run側にはVertex AI (Gemini 2.5 Flash) を使った本物のレポート生成コード、Firestoreへの保存コードが**既に完成している**が、エンジンからCloud Runへのプロキシが未実装のため繋がっていない。

**ゴール**: エンジンの `POST /api/reports/generate` で、`sync_enabled` がオンの時にCloud Runへプロキシし、AI生成レポートを返すようにする。

## データフロー（実装後）

```
Report.tsx → Engine /api/reports/generate
               → compute_daily_stats() (ローカルSQLite)
               → sync_enabled ?
                   YES → httpx POST → Cloud Run /api/reports/generate (JWT認証)
                                        → Vertex AI Gemini 2.5 Flash
                                        → Firestore保存
                                        ← AI生成レポート返却
                   NO  → ローカルダミーレポート（現状維持）
```

## 実装タスク

### 1. エンジン依存追加: `httpx`
- **File**: `engine/pyproject.toml`
- dependenciesに `"httpx>=0.27"` を追加

### 2. EngineConfigにクラウド接続フィールド追加
- **File**: `engine/engine/config.py`
- `sync_enabled` の後に3フィールド追加:
  - `cloud_run_url: str = ""` — Cloud RunのURL
  - `cloud_auth_token: str = ""` — JWT
  - `cloud_auth_email: str = ""` — ログイン中のメール（表示用）

### 3. Cloud Runクライアント新規作成
- **File (NEW)**: `engine/engine/api/cloud_client.py`
- `httpx.AsyncClient` を使った3関数:
  - `cloud_login(base_url, email, password)` → JWT取得
  - `cloud_register(base_url, email, password)` → 新規登録+JWT取得
  - `cloud_generate_report(base_url, token, stats)` → レポート生成プロキシ
- タイムアウト: 接続10秒、レポート生成60秒（Vertex AI + Cold Start対策）
- エラー時は `None` を返し、呼び出し元でローカルフォールバック

### 4. エンジンルート修正
- **File**: `engine/engine/api/routes.py`
- **(a)** `generate_report()` のTODO部分をプロキシ実装に置換:
  - `sync_enabled && cloud_run_url && cloud_auth_token` → Cloud Runへプロキシ
  - 失敗時 → ローカルダミーにフォールバック
  - `report_source: "cloud" | "local"` をレスポンスに追加
- **(b)** クラウド認証エンドポイント3つ追加:
  - `POST /api/cloud/login` — Cloud Runログイン代理、JWT保存
  - `POST /api/cloud/register` — Cloud Run新規登録代理、JWT保存
  - `POST /api/cloud/logout` — 認証情報クリア
- **(c)** `SettingsResponse` / `SettingsUpdate` に `cloud_run_url`, `cloud_auth_email` 追加

### 5. フロントエンド型定義追加
- **File**: `client/src/lib/types.ts`
- `Settings` に `cloud_run_url?`, `cloud_auth_email?` 追加
- `CloudAuthRequest`, `CloudAuthResponse` インターフェース追加

### 6. フロントエンドAPI追加
- **File**: `client/src/lib/api.ts`
- `cloudLogin()`, `cloudRegister()`, `cloudLogout()` メソッド追加

### 7. Settings UIにクラウド設定セクション追加
- **File**: `client/src/pages/Settings.tsx`
- **File**: `client/src/contexts/SettingsContext.tsx` (DEFAULT_SETTINGSに新フィールド)
- sync_enabledトグルの下に展開セクション:
  - Cloud Run URL入力欄
  - 未ログイン: メール/パスワード + ログイン/新規登録ボタン
  - ログイン中: `"user@example.com としてログイン中"` + ログアウトボタン

### 8. Report.tsx にフォールバック警告表示を追加
- **File**: `client/src/pages/Report.tsx`
- レスポンスの `report_source` を判定
- `sync_enabled` がオンなのに `report_source === "local"` の場合、レポート上部に警告バナーを表示:
  - 「Cloud Runに接続できませんでした。ローカルレポートを表示しています。」

### 9. README.mdにセキュリティ注意事項を追記
- **File**: `README.md`
- 「セキュリティに関する注意」セクションを追加:
  - Cloud Run認証トークン（JWT）は `~/.local-sidekick/config.json` にプレーンテキストで保存される
  - ハッカソンデモ用の暫定実装であり、本番運用ではシステムキーチェーン等の安全なストレージに移行が必要
  - config.jsonをバージョン管理に含めないこと（.gitignoreで除外済み）

### 10. GCPデプロイ・検証
- Cloud Runデプロイ（`server/deploy/cloudbuild.yaml` 使用）
- 環境変数設定: `GCP_PROJECT_ID`, `GCP_LOCATION=asia-northeast1`, `JWT_SECRET`
- Vertex AI API有効化確認
- エンドツーエンドテスト

## 主要ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `engine/pyproject.toml` | httpx追加 |
| `engine/engine/config.py` | 3フィールド追加 |
| `engine/engine/api/cloud_client.py` | **新規** - HTTPクライアント |
| `engine/engine/api/routes.py` | プロキシ実装 + 認証EP追加 |
| `client/src/lib/types.ts` | 型追加 |
| `client/src/lib/api.ts` | API追加 |
| `client/src/contexts/SettingsContext.tsx` | デフォルト更新 |
| `client/src/pages/Settings.tsx` | クラウド設定UI |
| `client/src/pages/Report.tsx` | フォールバック警告バナー |
| `README.md` | セキュリティ注意事項追記 |

## 参照ファイル（変更なし）

| ファイル | 参照理由 |
|---------|---------|
| `server/server/models/schemas.py` | ReportRequest / DailyReport スキーマ |
| `server/server/api/reports.py` | Cloud Run側エンドポイント |
| `server/server/services/vertex_ai.py` | Vertex AI実装 |
| `server/server/services/firestore_client.py` | Firestore保存 |
| `engine/engine/history/aggregator.py` | compute_daily_stats() 出力形式 |

## 設計判断

- **JWT有効期限**: 7日間（サーバ側設定）。期限切れ時は401を返し、ユーザーに再ログインを促す。ハッカソンではこれで十分
- **Cloud Runが到達不能な場合**: ローカルダミーにフォールバックし、レポートUI上に「Cloud Runに接続できませんでした。ローカルレポートを表示しています」等の警告メッセージを表示する。`report_source: "local"` をフロントエンドで判定し、`sync_enabled` かつ `report_source === "local"` の場合に警告バナーを出す
- **CORS不要**: エンジン→Cloud Runはサーバ間通信（ブラウザ経由ではない）
- **トークン保存**: `~/.local-sidekick/config.json` にプレーンテキスト（ハッカソン向け。本番ではシステムキーチェーン使用）。**README.mdにセキュリティ上の注意として明記する**

## 検証手順

1. `cd engine && pip install -e .` で httpx を含む依存インストール
2. `cd server && docker compose -f docker-compose.yml -f docker-compose.vertex.yml up` でCloud Runローカル起動
3. エンジン起動、Settings画面でCloud Run URLを入力しログイン
4. Report画面で「レポートを生成」→ AIレポートが返ることを確認
5. Cloud Runを停止した状態で再度生成 → ダミーレポートにフォールバック+警告バナー表示を確認
6. GCPにデプロイ後、Cloud Run URLを本番に切り替えて同様に確認

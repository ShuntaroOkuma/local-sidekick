# 5分バケット集計ロジックのバックエンド移行計画

> **Status: 実装完了** — [PR #32](https://github.com/ShuntaroOkuma/local-sidekick/pull/32) にて全Step (1a, 1b, 2, 3) をマージ済み (2026-02-14)

## Context

Timelineの表示改善で導入した「5分バケット → 多数決 → マージ」ロジック（現在のgit diffにある実装）が、通知やレポートにも有効であることが判明した。現在このロジックはフロントエンド（TypeScript）にのみ存在するため、バックエンド（Python）に移植し、通知・レポート・Timelineの全てで共有する。

**現状の問題:**
- 通知: 生データの「連続N秒」判定はノイズに弱く、通知がほぼ発火しない
- レポート: 生データ数千行をそのまま集計しており、LLMへの入力も冗長
- Timeline: フロントで毎回バケット計算を実行している（レスポンスサイズも大きい）

**目指す姿:**
- バックエンドに共通の5分バケットロジックを置く
- 通知・レポート・Timeline全てがこのロジックを利用する

---

## Step 1a: バックエンドに5分バケットロジック追加 + API

### 変更ファイル

**`engine/engine/history/aggregator.py`** — バケットロジック追加

新規関数 `build_bucketed_segments()`:
```python
def build_bucketed_segments(
    logs: list[dict],
    bucket_minutes: int = 5,
    max_entry_duration: float = 30.0,
) -> list[dict]:
```

- 入力: `get_state_log()` が返す生データ（`[{timestamp, integrated_state, ...}]`）
- 処理: フロントの `buildSegments` と同一のアルゴリズム
  1. 各エントリを5分バケットに振り分け（duration = min(next_ts - ts, 30s)）
  2. バケット内の多数決で代表状態を決定
  3. 連続する同一状態バケットをマージ
  4. データのないバケットはスキップ（空白）
- 出力:
```python
[
    {
        "state": "focused",
        "start_time": 1707886800.0,  # unix timestamp
        "end_time": 1707888600.0,
        "duration_min": 30,
        "breakdown": {"focused": 1500.0, "distracted": 60.0}  # state → seconds
    },
    ...
]
```

既存の `compute_daily_stats()` はこの時点では変更しない（Step 3で対応）。

**`engine/engine/api/routes.py`** — 新規エンドポイント

```python
@router.get("/history/bucketed")
async def get_history_bucketed(
    start: float = Query(...),
    end: float = Query(...),
    bucket_minutes: int = Query(5, ge=1, le=60),
) -> dict:
```

- `get_state_log(start, end)` → `build_bucketed_segments()` → JSON返却
- レスポンス: `{"segments": [...], "count": N}`

### テスト

**`engine/tests/test_bucketed_segments.py`** — 新規

- 空データ → 空リスト
- 単一バケット内の多数決
- 連続バケットのマージ
- データギャップ → セグメントが分断されること
- breakdown の合算が正しいこと

### 検証方法

```bash
cd engine && python -m pytest tests/test_bucketed_segments.py -v
```

エンジン起動後:
```bash
curl "http://localhost:18080/api/history/bucketed?start=1707800000&end=1707886400"
```

---

## Step 1b: フロントエンドを新APIに切り替え

### 変更ファイル

**`client/src/lib/api.ts`** — 新メソッド追加

```typescript
async getHistoryBucketed(range: { start: number; end: number }): Promise<BucketedSegment[]>
```

**`client/src/lib/types.ts`** — 新型定義

```typescript
interface BucketedSegment {
  state: string;
  start_time: number;
  end_time: number;
  duration_min: number;
  breakdown: Record<string, number>;
}
```

**`client/src/pages/Timeline.tsx`**

- `api.getHistory()` → `api.getHistoryBucketed()` に変更
- `HistoryEntry[]` ではなく `BucketedSegment[]` を TimelineChart に渡す

**`client/src/components/TimelineChart.tsx`**

- `buildSegments()` 関数を削除
- props を `BucketedSegment[]` を直接受け取る形に変更
- `Segment` インターフェースを `BucketedSegment` に統合
- ホバーツールチップはそのまま（`breakdown` はAPIから来る）

### 検証方法

```bash
cd client && npx electron-vite build
```

アプリ起動してTimelineページを確認。従来と同じ表示になること。

---

## Step 2: 通知ロジックを5分バケットベースに移行

**前提: Step 1a の `build_bucketed_segments()` が必要。**

### 設計

現在の `NotificationEngine.evaluate()` は `_integration_loop` から10秒ごとに呼ばれ、連続状態の秒数を追跡する（ノイズに弱い）。これを5分バケットベースに変更し、`build_bucketed_segments()` を共通ロジックとして利用する。

**アプローチ:** `evaluate()` を廃止し、5分間隔の専用ループ `_notification_loop` を新設。ループ内で `build_bucketed_segments()` を使って直近の履歴をバケット集計し、通知条件を判定する。

```
変更前:
  _integration_loop (10秒毎) → 分類 → DB保存 → evaluate(state) → 通知判定

変更後:
  _integration_loop (10秒毎) → 分類 → DB保存 → WebSocket通知（通知判定を除去）
  _notification_loop (5分毎) → store.get_state_log(直近90分)
                              → build_bucketed_segments()
                              → 通知条件判定 → 通知発火
```

### 変更ファイル

**`engine/engine/notification/engine.py`**

主な変更:
- `evaluate()` を廃止（ストリーミング型の状態追跡を全て除去）
- `_consecutive_state`, `_consecutive_start`, `_state_history` を廃止
- 新メソッド `check_buckets()`:
  ```python
  def check_buckets(
      self,
      segments: list[dict],  # build_bucketed_segments() の出力
      now: float,
  ) -> Optional[Notification]:
  ```
  - 入力: `build_bucketed_segments()` が返すセグメントリスト
  - ロジック:
    1. セグメントリストの末尾から直近のバケットを確認
    2. 判定条件:
       - drowsy: 直近2バケット（10分）が全てdrowsy → 通知
       - distracted: 直近2バケット（10分）が全てdistracted → 通知
       - over_focus: 直近18バケット（90分）中16バケット以上がfocused → 通知
    3. クールダウンチェック（既存ロジック維持）
  - **ステートレス**: クールダウン時刻のみ保持、バケット蓄積の内部状態は不要
- `reset_consecutive()` → `reset()` にリネーム（クールダウンタイマーのリセットのみ）
- `record_user_action()` はそのまま維持

**パラメータの変更:**

| パラメータ | 旧 | 新 |
|-----------|----|----|
| drowsy_trigger | 120秒連続 | 直近2バケット連続 (10分) |
| distracted_trigger | 120秒連続 | 直近2バケット連続 (10分) |
| over_focus判定 | 90分窓で80分focused | 直近18バケット中16バケットfocused |

コンストラクタの引数名は変更する（`drowsy_trigger_seconds` → `drowsy_trigger_buckets` 等）。`_config` と `main.py` の `_create_notification_engine()` も更新。

**`engine/engine/main.py`**

- `_integration_loop` から通知判定（`_notification_engine.evaluate()` 呼び出し）を除去
- 新規 `_notification_loop` を追加:
  ```python
  async def _notification_loop() -> None:
      """Background task: check notifications every 5 minutes using bucketed segments."""
      while True:
          await asyncio.sleep(300)  # 5分
          now = time.time()
          window_start = now - 90 * 60  # 直近90分
          logs = await _history_store.get_state_log(window_start, now)
          logs.sort(key=lambda x: x["timestamp"])
          segments = build_bucketed_segments(logs)

          notification = _notification_engine.check_buckets(segments, now)
          if notification is not None:
              await _history_store.log_notification(...)
              await broadcast_notification(...)
  ```
- `_notification_loop` を `_monitoring_tasks` に追加
- `_create_notification_engine()` の引数調整
- `apply_config()` でのリセット処理を更新
- `_on_resume()` での `reset_consecutive()` → `reset()` に変更

**`engine/engine/config.py`** — 設定項目名の更新

- `drowsy_trigger_seconds` → `drowsy_trigger_buckets: int = 2`
- `distracted_trigger_seconds` → `distracted_trigger_buckets: int = 2`
- `over_focus_window_minutes` → `over_focus_window_buckets: int = 18`
- `over_focus_threshold_minutes` → `over_focus_threshold_buckets: int = 16`
- クールダウン設定はそのまま維持

### テスト

**`engine/tests/test_notification_engine.py`** — 既存テスト更新 + 新テスト

- `check_buckets()` に `build_bucketed_segments()` の出力形式のセグメントリストを渡す形式に変更
- 直近2セグメントが連続drowsy → 通知発火
- 直近1セグメントだけdrowsy → 発火しない
- 直近2セグメントのうち1つがfocused → 発火しない
- over_focus: 18セグメント中16がfocused → 発火
- over_focus: 18セグメント中15がfocused → 発火しない
- クールダウン中は発火しない
- `reset()` → クールダウンタイマーがリセットされる

### 検証方法

```bash
cd engine && python -m pytest tests/test_notification_engine.py -v
```

実機: カメラ前で10分間目を閉じ気味にして drowsy 通知が来ることを確認。

---

## Step 3: レポートを5分バケットベースに移行

### 変更ファイル

**`engine/engine/history/aggregator.py`**

`compute_daily_stats()` を `build_bucketed_segments()` ベースに書き換え:

```python
async def compute_daily_stats(store, date=None) -> dict:
    logs = await store.get_state_log(start, end, limit=100000)
    logs.sort(key=lambda x: x["timestamp"])

    segments = build_bucketed_segments(logs)

    # segments から集計
    state_minutes = {"focused": 0, "drowsy": 0, ...}
    for seg in segments:
        state_minutes[seg["state"]] += seg["duration_min"]

    # focus_blocks = 連続 focused セグメント (>= 5分)
    focus_blocks = _extract_focus_blocks_from_segments(segments)

    return { ... }
```

- `_extract_focus_blocks()` を `_extract_focus_blocks_from_segments()` に置換
  - 生データではなくセグメントから集中ブロックを抽出
  - ロジックがシンプルになる（セグメント自体が既にマージ済み）

**`engine/engine/api/cloud_client.py`**

- `cloud_generate_report()` のペイロードに `segments` を追加
  - クラウド側のLLMが5分バケット済みのセグメントデータを受け取れるようにする
  - 既存の `focused_minutes` 等もそのまま送る（後方互換）

### テスト

- `compute_daily_stats()` のテスト更新
- バケット済みデータからの集計値が従来と近似していることを確認

### 検証方法

```bash
curl "http://localhost:18080/api/daily-stats?date=2026-02-14"
curl -X POST "http://localhost:18080/api/reports/generate?date=2026-02-14"
```

---

## 実装順序とリスク

```
Step 1a (バックエンド追加)    ← 既存機能に影響なし、安全。全Stepの基盤。
    ↓
    ├── Step 1b (フロント切替)   ← Timeline表示のみ影響、すぐ確認可能
    ├── Step 2 (通知移行)        ← build_bucketed_segments() を利用、テストで担保
    └── Step 3 (レポート移行)    ← 集計方法変更、値が近似であることを確認
```

Step 1a 完了後、Step 1b / 2 / 3 は**並列実行可能**（ファイル競合なし）。
各Stepでブランチを切り、PRを出す想定。

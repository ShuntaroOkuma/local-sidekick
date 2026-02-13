# 修正版E: 統合ルール判定 + 統合LLM判定

## Context

現在の状態推定は「カメラ独立判定 → PC独立判定 → 12パターンテーブルで統合」という3段構成。
カメラとPCがバラバラに判定するため、文脈をまたいだ推論（Zoom + 横向き = MTG中）ができない。

**新アーキテクチャ**: カメラとPCの生データを**まとめて**ルール判定 or LLM判定する。
統合テーブル（integrator.py）は不要になる。

```
現在:
  Camera loop → classify_camera → camera_state ─┐
  PC loop → classify_pc → pc_state ─────────────┤
  Integration loop: 12-pattern table ────────────→ final_state

新:
  Camera loop → store raw snapshot (判定しない)
  PC loop → store raw snapshot (判定しない)
  Classification loop:
    両方のsnapshotを取得
    → 統合ルール(明白ケース) → final_state
    → 統合LLM(曖昧ケース)  → final_state
```

## 変更対象ファイル

| ファイル | 変更 |
|---|---|
| `engine/engine/estimation/rule_classifier.py` | 統合ルール関数に書き換え |
| `engine/engine/estimation/prompts.py` | 統合プロンプト1本に書き換え |
| `engine/engine/estimation/integrator.py` | 12パターンテーブル削除、ヘルパーに簡素化 |
| `engine/engine/main.py` | ループ構成変更（収集と判定を分離） |
| `engine/tests/` (新規) | テスト |

変更**しない**: `llm_backend.py`, `config.py`, `camera/`, `pcusage/`, フロントエンド

---

## 1. rule_classifier.py — 統合ルール関数

既存の `classify_camera_text()` / `classify_pc_usage()` を削除し、
両方のデータを受け取る統合関数に置き換える。

### classify_unified(camera, pc) → Optional[ClassificationResult]

カメラとPCの**両方**を見て明白なケースのみ判定。それ以外はNone（LLMへ）。

| # | 条件 | 結果 | conf |
|---|---|---|---|
| 1 | camera: face_detected=False | away | 1.0 |
| 2 | camera: face_not_detected_ratio > 0.7 | away | 0.9 |
| 3 | camera: EAR>0.27 + yaw<25° + pitch<25° + perclos_drowsy=False + yawning=False **AND** pc: not idle | focused | 0.9 |
| — | 上記に該当しない | None (LLM) | — |

**PC idle単体ではidle判定しない**: MTGやオンラインコース受講中はPC操作なしで60秒以上
経つが、カメラでは画面を見ている。PC idle + カメラの状態を総合してLLMが判断する
（idle/focused/drowsy等を文脈で決定）。

**Rule 3が統合ルール**: カメラの明白なfocused信号 + PCがアイドルでない → focused。
カメラだけでは「画面を見ているが操作していない（寝落ち手前）」が区別できないため、
PC not idleを組み合わせることで信頼度を担保する。

### classify_unified_fallback(camera, pc) → ClassificationResult

LLM不可時のフォールバック。常にClassificationResultを返す（Noneなし）。

- camera: perclos_drowsy + yawning → drowsy (0.7)
- camera: yawning → drowsy (0.6)
- camera: yaw > 45° → distracted (0.6)
- pc: app_switches > 6 and unique_apps > 4 → distracted (0.6)
- それ以外 → focused (0.5)

### 片方のデータがない場合

- cameraがNone: ルール該当なし → LLMへ（PC idle単体ではidle判定しない）
- pcがNone: camera awayルールのみ適用、それ以外はLLMへ
- 両方None: unknown (0.0)

---

## 2. prompts.py — 統合プロンプト1本化

TEXT_SYSTEM_PROMPT / PC_USAGE_SYSTEM_PROMPT を削除し、UNIFIED_SYSTEM_PROMPT に統合。

### UNIFIED_SYSTEM_PROMPT

```
You are a focus/attention state classifier. Given BOTH facial feature data
AND PC usage data, determine the person's current state.

STATES:
- "focused": Engaged in work. Includes: looking at screen, talking to a
  colleague (head turned ~30-40° is normal), attending video meeting,
  reading, thinking with low input.
- "drowsy": Physical sleepiness. Requires MULTIPLE indicators together:
  very low eye openness (EAR < 0.22), high PERCLOS, yawning, drooping head.
  A single indicator alone is NOT enough.
- "distracted": Attention has genuinely drifted. Sustained purposeless
  gaze away, passive content scrolling, rapid unfocused app switching.
- "away": Person not present (no face detected).
- "idle": Stepped away from active work. Requires BOTH low/no PC input AND
  no sign of intentional engagement (not watching screen attentively, not
  in a meeting). PC idle alone does NOT mean idle — the person may be
  watching a video, in a meeting, or reading.

CROSS-SIGNAL REASONING (critical):
- Meeting app (Zoom/Teams/Meet/Slack huddle) active + head turned +
  low keyboard = attending a meeting → FOCUSED
- Head turned 30-40° + stable gaze + normal EAR = talking to colleague → FOCUSED
- Browser + high mouse + very low keyboard + long since last keystroke
  = passive scrolling → DISTRACTED
- Low EAR + PERCLOS + yawning + low input together = DROWSY
- Code editor + active keyboard + brief head turns = normal coding → FOCUSED

FACIAL DATA FIELDS:
- ear_average: Eye Aspect Ratio (0.25-0.35 normal; lower = more closed)
- perclos / perclos_drowsy: Eye closure ratio (True = potentially drowsy)
- yawning: Mouth indicates yawning
- head_pose.yaw: Left/right turn degrees (0 = facing screen)
- head_pose.pitch: Up/down tilt degrees
- gaze_off_screen_ratio: Fraction looking away
- blinks_per_minute: Normal 15-20/min
- head_movement_count: Significant position changes

PC DATA FIELDS:
- active_app: Currently focused application
- idle_seconds: Seconds since last input
- keyboard_rate_window / mouse_rate_window: Input rates (60s window)
- app_switches_in_window / unique_apps_in_window: App switching frequency
- seconds_since_last_keyboard: Recency of typing

Output ONLY JSON: {"state":"...","confidence":0.0-1.0,"reasoning":"brief"}
```

### Few-shot例（3つ）

```
Example 1 (MTG中):
Camera: {"face_detected":true,"ear_average":0.28,"head_pose":{"yaw":32,"pitch":-2},"perclos_drowsy":false,"yawning":false}
PC: {"active_app":"Zoom","idle_seconds":12,"keyboard_rate_window":0,"mouse_rate_window":5}
→ {"state":"focused","confidence":0.85,"reasoning":"Head turned but Zoom is active, likely in a meeting"}

Example 2 (パッシブ閲覧):
Camera: {"face_detected":true,"ear_average":0.30,"head_pose":{"yaw":3,"pitch":-5},"perclos_drowsy":false,"yawning":false}
PC: {"active_app":"Safari","idle_seconds":3,"keyboard_rate_window":1,"mouse_rate_window":180,"seconds_since_last_keyboard":55}
→ {"state":"distracted","confidence":0.75,"reasoning":"Facing screen but passive mouse-only browsing with almost no keyboard input"}

Example 3 (眠気):
Camera: {"face_detected":true,"ear_average":0.19,"perclos_drowsy":true,"yawning":true,"head_pose":{"yaw":-2,"pitch":15},"blinks_per_minute":8}
PC: {"active_app":"Code","idle_seconds":25,"keyboard_rate_window":3,"mouse_rate_window":2}
→ {"state":"drowsy","confidence":0.95,"reasoning":"Multiple strong drowsy signals despite being in editor: very low EAR, PERCLOS, yawning, low blink rate"}
```

### format_unified_prompt(camera_json, pc_json) → str

```python
UNIFIED_USER_PROMPT_TEMPLATE = """Classify the person's state using both data sources:

Facial features:
{camera_json}

PC usage:
{pc_json}

Respond with ONLY a JSON object."""

def format_unified_prompt(camera_json: str, pc_json: str) -> str:
    return UNIFIED_USER_PROMPT_TEMPLATE.format(
        camera_json=camera_json, pc_json=pc_json,
    )
```

片方がない場合は `"(unavailable)"` を渡す。

---

## 3. integrator.py — 簡素化

12パターンテーブルと `StateIntegrator.integrate()` のテーブルルックアップを削除。
`IntegratedState` dataclassは **API互換のため残す**（WebSocket、history、フロントエンド）。

ヘルパー関数に簡素化:

```python
def build_integrated_state(
    result: ClassificationResult,
    camera_snapshot: Optional[dict],
    pc_snapshot: Optional[dict],
) -> IntegratedState:
    """ClassificationResultからIntegratedStateを構築する。"""
    return IntegratedState(
        state=result.state,
        confidence=result.confidence,
        camera_state=None,   # 統合判定では個別状態なし
        pc_state=None,
        reasoning=result.reasoning,
        timestamp=time.time(),
    )
```

`camera_state`/`pc_state` はNone。フロントエンドではこれらのフィールドがnullの場合、
表示が空になるだけ（`{state.camera_state}` → 空文字列）。DB側もnullable。

---

## 4. main.py — ループ構成変更

### 変更の概要

| ループ | 現在 | 新 |
|---|---|---|
| `_camera_loop` | フレーム取得 + 特徴抽出 + **分類** | フレーム取得 + 特徴抽出 + **snapshot保存のみ** |
| `_pc_monitor_loop` | ポーリング + **分類** | ポーリング + **snapshot保存のみ** |
| `_integration_loop` | integrator.integrate() | **統合ルール → 統合LLM → IntegratedState構築** |

### グローバル変数の変更

```python
# 削除
_latest_camera_state: Optional[ClassificationResult] = None
_latest_pc_state: Optional[ClassificationResult] = None
_integrator = StateIntegrator()

# 追加
_latest_camera_snapshot: Optional[dict] = None   # TrackerSnapshot.to_dict()
_latest_pc_snapshot: Optional[dict] = None        # UsageSnapshot.to_dict()
```

### _camera_loop() の変更

5秒間隔の推定ブロック（L209-252）を簡素化:
```python
# 現在: ルール判定 → LLMフォールバック → _latest_camera_state に格納
# 新: snapshotをdictにして保存するだけ
if now - last_estimation >= _config.estimation_interval:
    last_estimation = now
    _latest_camera_snapshot = snapshot.to_dict()
```

分類ロジック全体（rule → LLM → ClassificationResult構築）を削除。

### _pc_monitor_loop() の変更

30秒間隔の推定ブロック（L288-338）を簡素化:
```python
# 現在: ルール判定 → LLMフォールバック → _latest_pc_state に格納
# 新: snapshotをdictにして保存するだけ
if now - last_estimation >= _config.pc_estimation_interval:
    last_estimation = now
    _latest_pc_snapshot = snapshot.to_dict()
```

### _integration_loop() の変更

現在の integrator.integrate() 呼び出しを、統合判定ロジックに置き換え:

```python
async def _integration_loop():
    _notification_engine = _create_notification_engine(_config)

    while _should_monitor:
        if _paused:
            await asyncio.sleep(1.0)
            continue

        camera_snap = _latest_camera_snapshot
        pc_snap = _latest_pc_snapshot

        if camera_snap is None and pc_snap is None:
            await asyncio.sleep(_config.integration_interval)
            continue

        # 1. 統合ルール（明白ケース）
        rule_result = classify_unified(camera_snap, pc_snap)
        if rule_result is not None:
            final = rule_result
        else:
            # 2. 統合LLM（曖昧ケース）
            llm = await _get_shared_llm(_config)
            if llm is None:
                final = classify_unified_fallback(camera_snap, pc_snap)
            else:
                camera_json = json.dumps(camera_snap, indent=2) if camera_snap else "(unavailable)"
                pc_json = json.dumps(pc_snap, indent=2) if pc_snap else "(unavailable)"
                user_prompt = format_unified_prompt(camera_json, pc_json)

                try:
                    async with _llm_lock:
                        result = await asyncio.to_thread(
                            llm.classify, UNIFIED_SYSTEM_PROMPT, user_prompt,
                        )
                    final = ClassificationResult(
                        state=result.get("state", "unknown"),
                        confidence=result.get("confidence", 0.5),
                        reasoning=result.get("reasoning", ""),
                        source="llm",
                    )
                except Exception as e:
                    logger.error("Unified LLM inference failed: %s", e)
                    final = classify_unified_fallback(camera_snap, pc_snap)

        # IntegratedState構築（API互換）
        integrated = IntegratedState(
            state=final.state,
            confidence=final.confidence,
            camera_state=None,
            pc_state=None,
            reasoning=final.reasoning,
            timestamp=time.time(),
        )

        # 以下は現行と同じ: broadcast, history, notification
        ...
```

### import変更

```python
# 削除
from engine.estimation.rule_classifier import classify_camera_text, classify_pc_usage
from engine.estimation.integrator import StateIntegrator

# 追加
from engine.estimation.rule_classifier import classify_unified, classify_unified_fallback
from engine.estimation.integrator import IntegratedState, build_integrated_state
from engine.estimation.prompts import UNIFIED_SYSTEM_PROMPT, format_unified_prompt
```

---

## 5. テスト

### engine/tests/test_rule_classifier.py

統合ルールのテスト:
- No face → away（PCデータ問わず）
- Camera focused + PC not idle → focused（**統合ルール**）
- PC idle > 60s + camera facing screen → None（LLMへ。MTG/動画視聴の可能性）
- Head turned 35° → None（LLMへ、distractedにしない）
- Drowsy signals → None（LLMへ）
- Safari + 低keyboard + 高mouse → None（LLMへ）
- Camera=None, PC idle → None（LLMへ。PC idle単体では判定しない）
- Camera away, PC=None → away
- 両方None → unknown

fallbackテスト:
- perclos_drowsy + yawning → drowsy
- yaw > 45° → distracted
- 極端app_switches → distracted
- その他 → focused (0.5)

### engine/tests/test_prompts.py

- format_unified_prompt: 両方あり、片方unavailable のフォーマット確認

---

## 6. 実装順序

1. **rule_classifier.py**: classify_unified / classify_unified_fallback を作成（旧関数は削除）
2. **prompts.py**: UNIFIED_SYSTEM_PROMPT + format_unified_prompt を作成（旧プロンプト削除）
3. **integrator.py**: 12パターンテーブル削除、build_integrated_state ヘルパーに簡素化
4. **main.py**: ループ構成変更（収集と判定の分離）
5. **テスト作成** + pytest実行

## 7. 検証方法

```bash
python -m pytest engine/tests/
python -m engine.main  # 起動して手動テスト
```

手動テスト項目:
- 正面で作業 → focused（統合ルール即判定）
- 離席 → away（ルール即判定）
- 頭を横に向けて会話 → focused（統合LLM: 横向き+操作あり→会話）
- Zoom起動中に横向き → focused（統合LLM: Zoom+横向き→MTG）
- Zoom起動中に操作なしで画面注視 → focused（統合LLM: Zoom+正面+idle→MTG視聴中）
- Safariでマウススクロール → distracted（統合LLM: mouse高+keyboard低→閲覧）
- 目閉じ+あくび → drowsy（統合LLM: 複合信号→眠気）
- 長時間操作なし+画面見ていない → idle（統合LLM: idle+カメラ曖昧→idle判定）
- model_tier=none → fallback関数が動作

## 注意事項

- `_latest_pc_snapshot` は30秒間隔更新なので、統合判定時に最大30秒のPC情報遅延がある。MTG検知には十分
- LLMプロンプトは英語（3Bモデルの英語理解 > 日本語）
- `IntegratedState.camera_state` / `pc_state` はNone固定。フロントエンドは空表示になる（破壊的変更なし）
- DB schema変更なし（camera_state, pc_state はnullable）

# Local Sidekick PoC Validation Plan

## Context

Local Sidekickは、常時カメラ観測+PC利用状況から眠気・集中・散漫を自動推定するmacOS常駐アプリ。コアコンセプトの技術的実現可能性を検証するため、以下3つの実験をPythonで実装する。

**検証項目:**
1. カメラ→顔特徴抽出→状態推定がオンデバイスLLM（llama.cpp / MLX直接組み込み）で可能か
2. 同上がLM Studio経由で可能か
3. PC利用状況をテキスト形式でLLMに渡して分析できるか

**環境:** Python / Apple Silicon M3-M4 (16-36GB RAM) / LM Studio インストール済み

---

## ディレクトリ構成

```
poc/
  pyproject.toml              # 依存関係定義
  download_models.py          # モデルダウンロードヘルパー

  shared/
    __init__.py
    camera.py                 # Webcam + MediaPipe FaceMesh パイプライン
    features.py               # 特徴量抽出（EAR, PERCLOS, 頭部姿勢, 瞬き, あくび）
    metrics.py                # パフォーマンス計測（FPS, レイテンシ, CPU/RAM）
    prompts.py                # LLMプロンプトテンプレート

  experiment1_embedded/       # 実験1: 組み込みLLM
    __init__.py
    run_text_llama_cpp.py     # 特徴量JSON → llama-cpp-python
    run_text_mlx.py           # 特徴量JSON → mlx-lm
    run_vision_llama_cpp.py   # カメラフレーム → llama-cpp-python (vision)
    run_vision_mlx.py         # カメラフレーム → mlx-vlm (vision)

  experiment2_lmstudio/       # 実験2: LM Studio経由
    __init__.py
    run_text_lmstudio.py      # 特徴量JSON → LM Studio API
    run_vision_lmstudio.py    # カメラフレーム → LM Studio Vision API

  experiment3_pcusage/        # 実験3: PC利用状況モニタリング
    __init__.py
    monitor.py                # データ収集（アプリ名, キーボード, マウス, アイドル）
    run_analysis.py           # 収集データ → LLM分析
```

---

## 実装ステップ

### Step 1: プロジェクトセットアップ
- `poc/pyproject.toml` を作成（依存関係をグループ分け）
- 仮想環境作成・依存インストール

**依存関係:**
| パッケージ | 用途 |
|-----------|------|
| `opencv-python` >=4.9 | カメラ取得・画像処理 |
| `mediapipe` >=0.10.14 | FaceMesh 468ランドマーク検出 |
| `numpy` >=1.26 | 数値計算 |
| `psutil` >=5.9 | CPU/メモリ計測 |
| `llama-cpp-python` >=0.3.0 | llama.cpp Pythonバインディング（Metal対応） |
| `mlx-lm` >=0.21 | Apple MLX テキスト生成 |
| `mlx-vlm` >=0.1.0 | Apple MLX ビジョンモデル |
| `openai` >=1.30 | LM Studio API クライアント |
| `pynput` >=1.7.6 | キーボード/マウスイベントカウント |
| `pyobjc-framework-Cocoa` >=10.0 | NSWorkspace（アクティブアプリ取得） |
| `pyobjc-framework-Quartz` >=10.0 | CGEventSource（アイドル時間） |
| `huggingface-hub` >=0.25 | モデルダウンロード |
| `Pillow` >=10.0 | 画像エンコーディング |

### Step 2: 共有モジュール実装

#### `shared/camera.py` - カメラ + FaceMeshパイプライン
- `CameraCapture` クラス: cv2.VideoCapture + MediaPipe FaceMesh
- 解像度640x480, `refine_landmarks=True`（虹彩ランドマーク含む478点）
- `read_frame()` → (BGRフレーム, ランドマーク or None)
- `get_frame_as_base64()` → JPEG圧縮→base64文字列
- 単体テスト: `python -m shared.camera --show-video --duration 10`

#### `shared/features.py` - 特徴量抽出
- **EAR（Eye Aspect Ratio）**: 右目[33,160,158,133,153,144], 左目[362,385,387,263,380,373]
  - 閾値: 0.20未満 → 目を閉じている
- **PERCLOS**: 60秒スライディングウィンドウでEAR<0.20のフレーム割合
  - 0.15超 → 眠気の兆候
- **瞬き検出**: EARが閾値を下回って戻るパターンを検出
  - 正常: 15-20回/60秒
- **MAR（Mouth Aspect Ratio）**: あくび検出用
  - 0.6超 → あくび
- **頭部姿勢推定**: cv2.solvePnPで6点のランドマークからpitch/yaw/roll算出
- `FeatureTracker` クラス: 時系列追跡（dequeベースのスライディングウィンドウ）

#### `shared/metrics.py` - パフォーマンス計測
- FPS, フレーム処理時間, LLMレイテンシ（平均・P95）, CPU%, メモリMB

#### `shared/prompts.py` - プロンプトテンプレート
- 特徴量JSON用: "facial features → state classification (focused/drowsy/distracted)"
- ビジョン用: "webcam image → state classification"
- PC利用状況用: "usage metadata → work state (focused/distracted/idle)"
- 全てJSON形式で応答するよう指示

### Step 3: モデルダウンロード

`download_models.py` で以下をダウンロード:

| モデル | フォーマット | サイズ | 用途 |
|--------|------------|--------|------|
| Qwen2.5-3B-Instruct | GGUF Q4_K_M | ~2.0GB | テキストLLM (llama.cpp) |
| Qwen2.5-3B-Instruct-4bit | MLX | ~1.8GB | テキストLLM (MLX) |
| Qwen2-VL-2B-Instruct | GGUF Q4_K_M | ~1.5GB | ビジョンLLM (llama.cpp) |
| Qwen2-VL-2B-Instruct-4bit | MLX | ~1.5GB | ビジョンLLM (MLX) |

合計: ~7-8GB

### Step 4: 実験1 - 組み込みLLM

4つのバリアントをそれぞれ実装・実行:

1. **run_text_llama_cpp.py**: カメラ→特徴量JSON→llama-cpp-python（Qwen2.5-3B）
   - `Llama(model_path=..., n_gpu_layers=-1, n_ctx=2048)` でMetal GPU活用
   - 5秒間隔でLLM呼び出し, 60秒間実行

2. **run_text_mlx.py**: カメラ→特徴量JSON→mlx-lm（Qwen2.5-3B-4bit）
   - `mlx_lm.load()` + `mlx_lm.generate()` でApple Silicon最適化推論
   - llama.cppとレイテンシ・スループットを比較

3. **run_vision_llama_cpp.py**: カメラフレーム→llama-cpp-python（Qwen2-VL-2B）
   - base64エンコードしたJPEGフレームをビジョンモデルに送信
   - 15秒間隔, 120秒間実行（ビジョンモデルは遅い）

4. **run_vision_mlx.py**: カメラフレーム→mlx-vlm（Qwen2-VL-2B-4bit）
   - PILイメージに変換して送信

### Step 5: 実験2 - LM Studio経由

2つのバリアントを実装:

1. **run_text_lmstudio.py**: 特徴量JSON → `http://localhost:1234/v1` (OpenAI互換API)
   - `openai.OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")`
   - 起動時にLM Studio接続チェック

2. **run_vision_lmstudio.py**: カメラフレーム → LM Studio Vision API
   - base64 data URI形式で画像を送信

**前提:** LM Studioで対応モデルを事前にロードしておく必要あり

### Step 6: 実験3 - PC利用状況モニタリング

1. **monitor.py**: `PCUsageMonitor` クラス
   - `NSWorkspace.sharedWorkspace().frontmostApplication().localizedName()` でアクティブアプリ取得
   - `pynput.keyboard.Listener` / `pynput.mouse.Listener` でイベント数カウント（入力内容は一切記録しない）
   - `CGEventSourceSecondsSinceLastEventType` でアイドル時間取得
   - アプリ切替検出（1秒ポーリング）
   - 必要権限の自動検出と案内表示
   - 単体テスト: `python -m experiment3_pcusage.monitor --duration 30`

2. **run_analysis.py**: モニタリングデータ → LLM分析
   - `--backend lmstudio|llama_cpp|mlx` で切替可能
   - 30秒間隔でスナップショット取得→LLM送信
   - 5分間実行

**必要なmacOS権限:**
- Input Monitoring（システム設定 > プライバシーとセキュリティ > 入力監視）: pynput用
- NSWorkspaceとCGEventSourceは権限不要

---

## 成功基準

### 実験1 - 組み込みLLM
| 指標 | テキストモード目標 | ビジョンモード目標 |
|------|-------------------|-------------------|
| カメラFPS（特徴量抽出含む） | >= 25 FPS | >= 25 FPS |
| LLMレイテンシ | < 2秒 | < 10秒 |
| メモリ使用量 | < 4GB | < 6GB |
| CPU使用率（持続） | < 50% | < 70% |
| 推定品質 | 明白な状態（目閉じ=眠気等）を70%以上正しく識別 | 同左 |

### 実験2 - LM Studio
| 指標 | 目標 |
|------|------|
| LLMレイテンシ（テキスト） | < 3秒 |
| LLMレイテンシ（ビジョン） | < 15秒 |
| 組み込みとの品質比較 | 同等 |
| 統合の容易さ | 組み込みより簡潔 |

### 実験3 - PC利用状況
| 指標 | 目標 |
|------|------|
| データ収集オーバーヘッド | < 1% CPU |
| 権限検出 | 必要な権限を検出・案内できる |
| LLM状態分類 | idle/distracted/focusedを正しく区別 |

### PoC全体の成功条件
1. テキスト or ビジョンの少なくとも1つで、実用的なレイテンシ+品質が確認できる
2. LM Studio統合が組み込みの代替として機能する
3. PC利用状況モニタリングが5分以上安定動作する
4. メモリ6GB以下で通常作業と共存可能

---

## 実行手順

```bash
cd /Users/s-ohkuma/code/pw/products/local-sidekick/poc

# 1. 環境セットアップ
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"

# 2. モデルダウンロード
python download_models.py

# 3. 共有モジュール動作確認
python -m shared.camera --show-video --duration 10
python -m experiment3_pcusage.monitor --duration 30

# 4. 実験1: 組み込みLLM
python -m experiment1_embedded.run_text_llama_cpp --duration 60 --interval 5
python -m experiment1_embedded.run_text_mlx --duration 60 --interval 5
python -m experiment1_embedded.run_vision_llama_cpp --duration 120 --interval 15
python -m experiment1_embedded.run_vision_mlx --duration 120 --interval 15

# 5. 実験2: LM Studio（事前にモデルをロード）
python -m experiment2_lmstudio.run_text_lmstudio --duration 60 --interval 5
python -m experiment2_lmstudio.run_vision_lmstudio --duration 120 --interval 15

# 6. 実験3: PC利用状況
python -m experiment3_pcusage.run_analysis --backend lmstudio --duration 300 --interval 30
```

---

## テストプロトコル（手動検証）

PoCが完成したら、以下のシナリオを実際に演じて結果を確認する。
各シナリオは**最低30秒間**維持し、LLMの推定結果と実際の状態が一致するかを記録する。

### テスト1: カメラ状態推定の精度検証

#### シナリオA: 集中状態（期待出力: `focused`）
- **やること**: 画面を正面から見つめ、姿勢を安定させ、自然に瞬きする
- **確認点**:
  - EARが0.25-0.35付近で安定しているか
  - head pitch/yawが小さい値（±5度以内）か
  - LLMが `focused` と判定するか

#### シナリオB: 眠気状態（期待出力: `drowsy`）
- **やること**: 以下を順番に試す
  1. ゆっくり目を閉じる（3-5秒間維持）→ EAR低下を確認
  2. 瞬きの頻度を意識的に増やす
  3. あくびをする → MAR上昇を確認
  4. 頭をゆっくり下に傾ける（うつむき）→ head pitch変化を確認
- **確認点**:
  - PERCLOSが0.15を超えるか
  - あくび時にMAR > 0.6が検出されるか
  - LLMが `drowsy` と判定するか

#### シナリオC: 散漫/よそ見状態（期待出力: `distracted`）
- **やること**:
  1. 顔を左右に大きく向ける（スマホを見るように）
  2. 上を向く、下を向く
  3. 椅子でそわそわ動く
- **確認点**:
  - head yaw/pitchが大きく変化するか
  - LLMが `distracted` と判定するか

#### シナリオD: 離席（期待出力: 顔未検出）
- **やること**: カメラの前から離れる（30秒間）
- **確認点**:
  - `face_detected: false` になるか
  - エラーやクラッシュなく処理が継続するか

#### シナリオE: エッジケース
- **やること**:
  1. メガネをかけた状態で全シナリオを再実行
  2. 部屋の照明を暗くする（間接照明のみ）
  3. 顔の半分を手で隠す
  4. カメラとの距離を変える（近い/遠い）
- **確認点**:
  - メガネ有無でEAR精度に差が出るか
  - 暗所でFaceMeshが動作するか（ランドマーク検出率）
  - 顔の一部が隠れた場合の挙動（クラッシュしないか）

### テスト2: PC利用状況モニタリングの精度検証

#### シナリオF: 集中作業（期待出力: `focused`）
- **やること**: エディタ or ターミナルを1つ開き、3分間コードを書く（アプリ切替なし）
- **確認点**:
  - keyboard_events_per_min が適度な値を示すか
  - app_switches が 0-1 か
  - LLMが `focused` と判定するか

#### シナリオG: 散漫（期待出力: `distracted`）
- **やること**: 2分間で意図的に以下を行う
  1. ブラウザ → Slack → エディタ → ブラウザ → メール → ... と高速にアプリ切替
  2. SNSやニュースサイトを巡回
- **確認点**:
  - app_switches_in_window が高い値（10以上）を示すか
  - unique_apps_in_window が多いか
  - LLMが `distracted` と判定するか

#### シナリオH: アイドル（期待出力: `idle`）
- **やること**: キーボード・マウスに30秒以上触れない
- **確認点**:
  - idle_seconds が正しく増加するか
  - keyboard/mouse events_per_min が 0 に近いか
  - LLMが `idle` と判定するか

### テスト3: パターン比較（組み込み vs LM Studio）

同じシナリオ（A〜C）を以下の各パターンで実行し、結果を比較する:

| 比較軸 | 記録する項目 |
|--------|-------------|
| **推定精度** | 各シナリオで正しい状態を返した割合（正答率） |
| **レイテンシ** | LLM応答時間の平均・最大値 |
| **リソース消費** | CPU%, メモリMB（Activity Monitorでも併せて確認） |
| **安定性** | テスト中のエラー・クラッシュ有無 |
| **応答の質** | LLMのreasoning（根拠説明）が妥当か |

比較対象:
1. llama-cpp-python テキストモード
2. mlx-lm テキストモード
3. LM Studio テキストモード
4. （余裕があれば）ビジョンモード各種

### テスト4: 総合テスト（カメラ + PC利用状況の併用）

> このテストは実験1-3が個別に成功した場合のみ実施

- **やること**: 実験1のカメラ推定と実験3のPC利用状況モニタリングを同時に起動し、5分間通常作業する
- **確認点**:
  - 2つのプロセスが同時に動作してもパフォーマンスに問題がないか
  - カメラ推定とPC利用状況推定の結果に矛盾がないか（例: カメラ=focused なのに PC=idle は矛盾）
  - 両方の信号を組み合わせることで、単独より精度が上がりそうか（定性的に判断）

### 結果記録テンプレート

各テストの結果を以下の形式で記録する:

```markdown
## テスト結果: [日付]

### 環境
- Mac: [モデル / チップ / RAM]
- OS: [バージョン]
- 照明: [自然光 / 蛍光灯 / 間接照明]
- メガネ: [あり / なし]

### シナリオ別結果
| シナリオ | パターン | 期待状態 | LLM出力 | 正答 | レイテンシ | 備考 |
|---------|---------|---------|---------|------|-----------|------|
| A: 集中 | llama.cpp text | focused | | | | |
| A: 集中 | mlx text | focused | | | | |
| A: 集中 | LM Studio text | focused | | | | |
| B: 眠気 | ... | drowsy | | | | |
| ... | | | | | | |

### パフォーマンス
| パターン | 平均FPS | 平均LLMレイテンシ | CPU% | メモリMB |
|---------|---------|-----------------|------|---------|
| llama.cpp text | | | | |
| mlx text | | | | |
| LM Studio text | | | | |

### 所感・判断
- 採用推奨パターン:
- 品質面の課題:
- パフォーマンス面の課題:
- MVP開発に向けた方針:
```

---

## リスクと対策

| リスク | 対策 |
|--------|------|
| MediaPipeがmacOS ARM未対応 | `mediapipe-silicon` forkまたはApple Vision Framework (PyObjC)にフォールバック |
| llama-cpp-python Metal コンパイル失敗 | pre-built wheelを使用、またはCPUのみで実行 |
| ビジョンモデルが遅すぎて実用的でない | テキスト特徴量アプローチを推奨として文書化。ビジョンは定期的な深い分析用に限定 |
| pynputがmacOS Sequoiaで動作しない | 起動時に権限検出、CGEventSourceのみフォールバック |
| LM Studioが起動していない/モデル未ロード | 起動時接続チェック+エラーメッセージ |

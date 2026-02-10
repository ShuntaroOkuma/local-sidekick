# Local Sidekick PoC

常時カメラ観測+PC利用状況から眠気・集中・散漫を自動推定するmacOS常駐アプリのPoC（概念実証）。

## 概要

3つの技術的仮説を検証します：

1. **実験1（組み込みLLM）**: MediaPipeで抽出した顔特徴量を、オンデバイスLLM（llama.cpp / MLX）で集中・眠気・散漫に分類できるか
2. **実験2（LM Studio）**: 同じ分類がLM StudioのOpenAI互換APIでも動作するか
3. **実験3（PC利用状況）**: OS レベルのメタデータ（アクティブアプリ、キーボード/マウス操作、アイドル時間）をLLMで分析し、集中・散漫・アイドルを検出できるか

**動作環境**: Python / Apple Silicon M3-M4（16-36GB RAM）/ macOS

## ディレクトリ構成

```
poc/
  pyproject.toml              # 依存関係（実験ごとにグループ化）
  download_models.py          # モデルダウンロードヘルパー（Qwen2.5/Qwen2-VL）

  shared/
    __init__.py
    camera.py                 # Webcam + MediaPipe FaceLandmarkerパイプライン
    features.py               # 特徴量抽出（EAR, PERCLOS, 頭部姿勢, 瞬き, あくび）
    metrics.py                # パフォーマンス計測（FPS, レイテンシ, CPU/RAM）
    prompts.py                # LLMプロンプトテンプレート

  experiment1_embedded/       # 実験1: 組み込みLLM
    __init__.py
    run_text_llama_cpp.py     # 特徴量JSON → llama-cpp-python
    run_text_mlx.py           # 特徴量JSON → mlx-lm
    run_vision_llama_cpp.py   # カメラフレーム → llama-cpp-python（ビジョン）
    run_vision_mlx.py         # カメラフレーム → mlx-vlm（ビジョン）

  experiment2_lmstudio/       # 実験2: LM Studio
    __init__.py
    run_text_lmstudio.py      # 特徴量JSON → LM Studio API
    run_vision_lmstudio.py    # カメラフレーム → LM Studio Vision API

  experiment3_pcusage/        # 実験3: PC利用状況モニタリング
    __init__.py
    monitor.py                # データ収集（アプリ名, キーボード, マウス, アイドル）
    run_analysis.py           # 収集データ → LLM分析
```

## セットアップ

### 前提条件

- Apple Silicon搭載macOS（M3/M4, 16GB以上のRAM）
- Python 3.11以上
- LM Studio（実験2用、インストール済みであること）

### インストール

```bash
cd poc/

# 仮想環境の作成
python3 -m venv .venv
source .venv/bin/activate

# 全依存関係のインストール
pip install -e ".[all]"

# モデルダウンロード（合計約7-8GB）
python download_models.py
```

### モデル一覧

| モデル | フォーマット | サイズ | 用途 |
|--------|------------|--------|------|
| Qwen2.5-3B-Instruct | GGUF Q4_K_M | 約2.0GB | テキストLLM（llama.cpp） |
| Qwen2.5-3B-Instruct-4bit | MLX | 約1.8GB | テキストLLM（MLX） |
| Qwen2-VL-2B-Instruct | GGUF Q4_K_M | 約1.5GB | ビジョンLLM（llama.cpp） |
| Qwen2-VL-2B-Instruct-4bit | MLX | 約1.5GB | ビジョンLLM（MLX） |

### macOS権限設定

- **カメラ**: カメラ実験全般に必要（初回実行時にダイアログ表示）
- **入力監視**（システム設定 > プライバシーとセキュリティ > 入力監視）: 実験3のpynputによるキーボード/マウスイベント取得に必要
- **アクセシビリティ**（システム設定 > プライバシーとセキュリティ > アクセシビリティ）: 実験3のCGEventSourceによるアイドル時間検出に必要

権限の詳細は [poc/README.ja.md](poc/README.ja.md) の「macOS権限設定」セクションを参照してください。

## 実験の実行

### 共有モジュール動作確認

```bash
# カメラ + FaceLandmarkerパイプラインの確認（10秒間映像表示）
python -m shared.camera --show-video --duration 10

# PC利用状況モニターの確認（30秒間データ収集）
python -m experiment3_pcusage.monitor --duration 30
```

### 実験1: 組み込みLLM

```bash
# テキストモード: 特徴量JSON → LLM
python -m experiment1_embedded.run_text_llama_cpp --duration 60 --interval 5
python -m experiment1_embedded.run_text_mlx --duration 60 --interval 5

# ビジョンモード: カメラフレーム → LLM（遅いため長い間隔）
python -m experiment1_embedded.run_vision_llama_cpp --duration 120 --interval 15
python -m experiment1_embedded.run_vision_mlx --duration 120 --interval 15
```

### 実験2: LM Studio

**前提**: LM Studioで対応モデルを事前にロードしておくこと。

```bash
# テキストモード
python -m experiment2_lmstudio.run_text_lmstudio --duration 60 --interval 5

# ビジョンモード
python -m experiment2_lmstudio.run_vision_lmstudio --duration 120 --interval 15
```

### 実験3: PC利用状況モニタリング

```bash
python -m experiment3_pcusage.run_analysis --backend lmstudio --duration 300 --interval 30
```

バックエンドオプション: `lmstudio`, `llama_cpp`, `mlx`

## 成功基準

### 実験1 - 組み込みLLM

| 指標 | テキストモード目標 | ビジョンモード目標 |
|------|-------------------|-------------------|
| カメラFPS（特徴量抽出含む） | 25 FPS以上 | 25 FPS以上 |
| LLMレイテンシ | 2秒未満 | 10秒未満 |
| メモリ使用量 | 4GB未満 | 6GB未満 |
| CPU使用率（持続） | 50%未満 | 70%未満 |
| 推定品質 | 明白な状態を70%以上正しく識別 | 同左 |

### 実験2 - LM Studio

| 指標 | 目標 |
|------|------|
| LLMレイテンシ（テキスト） | 3秒未満 |
| LLMレイテンシ（ビジョン） | 15秒未満 |
| 組み込みとの品質比較 | 同等 |
| 統合の容易さ | 組み込みより簡潔 |

### 実験3 - PC利用状況

| 指標 | 目標 |
|------|------|
| データ収集オーバーヘッド | CPU 1%未満 |
| 権限検出 | 必要な権限を検出・案内できる |
| 状態分類 | idle/distracted/focusedを正しく区別 |

### PoC全体の成功条件

1. テキスト or ビジョンの少なくとも1つで、実用的なレイテンシ+品質が確認できる
2. LM Studio統合が組み込みの代替として機能する
3. PC利用状況モニタリングが5分以上安定動作する
4. メモリ6GB以下で通常作業と共存可能

## リスクと対策

| リスク | 対策 |
|--------|------|
| MediaPipeがmacOS ARMで動作しない | `mediapipe-silicon` forkまたはApple Vision Framework（PyObjC）にフォールバック |
| llama-cpp-python Metalコンパイル失敗 | pre-built wheelを使用、またはCPUのみで実行 |
| ビジョンモデルが遅すぎて実用的でない | テキスト特徴量アプローチを推奨として文書化。ビジョンは定期的な深い分析用に限定 |
| pynputがmacOS Sequoiaで動作しない | 起動時に権限検出、CGEventSourceのみにフォールバック |
| LM Studioが未起動/モデル未ロード | 起動時接続チェック+エラーメッセージ |

## プライバシー設計

- **コンテンツ記録なし**: メタデータのみ収集（アプリ名、イベント数、アイドル時間）
- **キーロガーなし**: キーボードイベントの数のみ、入力内容は一切記録しない
- **スクリーンキャプチャなし**: カメラはユーザーの顔のみ、画面内容は撮影しない
- **オンデバイス処理**: 映像フレームはローカルで処理、外部に送信しない

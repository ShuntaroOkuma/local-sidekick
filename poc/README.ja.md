# Local Sidekick PoC

Webカメラ + Apple Silicon上のLLM推論による、オンデバイス眠気・集中・散漫検出。

## 概要

3つのコア機能を検証します：

1. **実験1（組み込みLLM）**: カメラ → 顔特徴量抽出 → オンデバイスLLM（llama.cpp / MLX）で状態推定
2. **実験2（LM Studio）**: 同じパイプラインをLM StudioのOpenAI互換APIで実行
3. **実験3（PC利用状況）**: OSレベルの操作監視（アクティブアプリ、キーボード/マウスイベント、アイドル時間）→ LLM分析

## 動作要件

- Apple Silicon搭載macOS（M3-M4, 16-36GB RAM）
- Python 3.11以上
- LM Studio（実験2用）

## クイックスタート

```bash
cd poc/

# 1. 仮想環境の作成と依存関係インストール
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"

# 2. モデルダウンロード（合計約7-8GB）
python download_models.py

# 3. カメラパイプラインの動作確認
python -m shared.camera --show-video --duration 10

# 4. 実験の実行
# 実験1: 組み込みLLM
python -m experiment1_embedded.run_text_llama_cpp --duration 60 --interval 5
python -m experiment1_embedded.run_text_mlx --duration 60 --interval 5
python -m experiment1_embedded.run_vision_llama_cpp --duration 120 --interval 15
python -m experiment1_embedded.run_vision_mlx --duration 120 --interval 15

# 実験2: LM Studio（事前にLM Studioでモデルをロード）
python -m experiment2_lmstudio.run_text_lmstudio --duration 60 --interval 5
python -m experiment2_lmstudio.run_vision_lmstudio --duration 120 --interval 15

# 実験3: PC利用状況モニタリング
python -m experiment3_pcusage.monitor --duration 30
python -m experiment3_pcusage.run_analysis --backend lmstudio --duration 300 --interval 30
```

## ディレクトリ構成

```
poc/
  pyproject.toml              # 依存関係定義
  download_models.py          # モデルダウンロードヘルパー

  shared/
    camera.py                 # Webcam + MediaPipe FaceLandmarkerパイプライン
    features.py               # 特徴量抽出（EAR, PERCLOS, 頭部姿勢, 瞬き, あくび）
    metrics.py                # パフォーマンス計測（FPS, レイテンシ, CPU/RAM）
    prompts.py                # LLMプロンプトテンプレート

  experiment1_embedded/       # 実験1: 組み込みLLM
    run_text_llama_cpp.py     # 特徴量JSON → llama-cpp-python
    run_text_mlx.py           # 特徴量JSON → mlx-lm
    run_vision_llama_cpp.py   # カメラフレーム → llama-cpp-python（ビジョン）
    run_vision_mlx.py         # カメラフレーム → mlx-vlm（ビジョン）

  experiment2_lmstudio/       # 実験2: LM Studio API
    run_text_lmstudio.py      # 特徴量JSON → LM Studio API
    run_vision_lmstudio.py    # カメラフレーム → LM Studio Vision API

  experiment3_pcusage/        # 実験3: PC利用状況モニタリング
    monitor.py                # データ収集（アプリ名, キーボード, マウス, アイドル）
    run_analysis.py           # 収集データ → LLM分析
```

## 成功基準

| 指標 | テキストモード | ビジョンモード |
|------|--------------|--------------|
| カメラFPS | 25以上 | 25以上 |
| LLMレイテンシ | 2秒未満（組み込み）/ 3秒未満（LM Studio） | 10秒未満（組み込み）/ 15秒未満（LM Studio） |
| メモリ | 4GB未満 | 6GB未満 |
| CPU（持続） | 50%未満 | 70%未満 |
| 推定精度 | 明白な状態を70%以上正しく識別 | 同左 |

## macOS権限設定

### カメラ（実験1, 2）

カメラへのアクセス許可が必要です。初回実行時にmacOSのダイアログが表示されます。

### 入力監視 / アクセシビリティ（実験3）

実験3（PC利用状況モニタリング）では、キーボード/マウスイベントの取得とアイドル時間の検出のために、**実行元のターミナルアプリ**にmacOS権限を付与する必要があります。

#### VSCode Terminal（推奨）

VSCodeターミナルでは、VSCode自体に権限があれば子プロセスも動作します。

1. **システム設定 > プライバシーとセキュリティ > 入力監視** に「Visual Studio Code」を追加・有効化
2. **システム設定 > プライバシーとセキュリティ > アクセシビリティ** に「Visual Studio Code」を追加・有効化

> 実行時に `This process is not trusted!` という警告が表示されますが、VSCodeに権限が付与されていればイベント取得は正常に動作します。この警告は無視して問題ありません。

#### iTerm2

iTerm2では以下の **3つの権限すべて** が必要です：

1. **システム設定 > プライバシーとセキュリティ > 入力監視** に「iTerm」を追加・有効化
2. **システム設定 > プライバシーとセキュリティ > アクセシビリティ** に「iTerm」を追加・有効化
3. **システム設定 > プライバシーとセキュリティ > オートメーション** でiTermの権限を確認

権限変更後は **ターミナルアプリを再起動** してください（既存プロセスには反映されません）。

#### Terminal.app

1. **システム設定 > プライバシーとセキュリティ > 入力監視** に「ターミナル」を追加・有効化
2. **システム設定 > プライバシーとセキュリティ > アクセシビリティ** に「ターミナル」を追加・有効化

#### 権限の確認方法

```bash
python -m experiment3_pcusage.monitor --duration 10
```

正常な場合：
```
Checking permissions...
[OK] All permissions granted.
```

権限不足の場合は `[WARNING] Some permissions are missing` と表示され、必要な権限が案内されます。

## モデル一覧

| モデル | フォーマット | サイズ | 用途 |
|--------|------------|--------|------|
| Qwen2.5-3B-Instruct | GGUF Q4_K_M | 約2.0GB | テキストLLM（llama.cpp） |
| Qwen2.5-3B-Instruct-4bit | MLX | 約1.8GB | テキストLLM（MLX） |
| Qwen2-VL-2B-Instruct | GGUF Q4_K_M | 約1.5GB | ビジョンLLM（llama.cpp） |
| Qwen2-VL-2B-Instruct-4bit | MLX | 約1.5GB | ビジョンLLM（MLX） |

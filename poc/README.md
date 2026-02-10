# Local Sidekick PoC

On-device drowsiness, focus, and distraction detection using webcam + LLM inference on Apple Silicon.

## Overview

This PoC validates three core capabilities:

1. **Experiment 1 (Embedded LLM)**: Camera -> facial feature extraction -> state estimation via on-device LLM (llama.cpp / MLX)
2. **Experiment 2 (LM Studio)**: Same pipeline using LM Studio's OpenAI-compatible API
3. **Experiment 3 (PC Usage)**: OS-level activity monitoring (active app, keyboard/mouse events, idle time) -> LLM analysis

## Requirements

- macOS with Apple Silicon (M3-M4, 16-36GB RAM)
- Python 3.11+
- LM Studio (for Experiment 2)

## Quick Start

```bash
cd poc/

# 1. Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"

# 2. Download models (~7-8GB total)
python download_models.py

# 3. Verify camera pipeline
python -m shared.camera --show-video --duration 10

# 4. Run experiments
# Experiment 1: Embedded LLM
python -m experiment1_embedded.run_text_llama_cpp --duration 60 --interval 5
python -m experiment1_embedded.run_text_mlx --duration 60 --interval 5
python -m experiment1_embedded.run_vision_llama_cpp --duration 120 --interval 15
python -m experiment1_embedded.run_vision_mlx --duration 120 --interval 15

# Experiment 2: LM Studio (load model in LM Studio first)
python -m experiment2_lmstudio.run_text_lmstudio --duration 60 --interval 5
python -m experiment2_lmstudio.run_vision_lmstudio --duration 120 --interval 15

# Experiment 3: PC Usage Monitoring
python -m experiment3_pcusage.monitor --duration 30
python -m experiment3_pcusage.run_analysis --backend lmstudio --duration 300 --interval 30
```

## Directory Structure

```
poc/
  pyproject.toml              # Dependencies
  download_models.py          # Model download helper

  shared/
    camera.py                 # Webcam + MediaPipe FaceMesh pipeline
    features.py               # Feature extraction (EAR, PERCLOS, head pose, blink, yawn)
    metrics.py                # Performance measurement (FPS, latency, CPU/RAM)
    prompts.py                # LLM prompt templates

  experiment1_embedded/       # Experiment 1: Embedded LLM
    run_text_llama_cpp.py     # Features JSON -> llama-cpp-python
    run_text_mlx.py           # Features JSON -> mlx-lm
    run_vision_llama_cpp.py   # Camera frame -> llama-cpp-python (vision)
    run_vision_mlx.py         # Camera frame -> mlx-vlm (vision)

  experiment2_lmstudio/       # Experiment 2: LM Studio API
    run_text_lmstudio.py      # Features JSON -> LM Studio API
    run_vision_lmstudio.py    # Camera frame -> LM Studio Vision API

  experiment3_pcusage/        # Experiment 3: PC Usage Monitoring
    monitor.py                # Data collection (app, keyboard, mouse, idle)
    run_analysis.py           # Collected data -> LLM analysis
```

## Success Criteria

| Metric             | Text Mode                         | Vision Mode                         |
| ------------------ | --------------------------------- | ----------------------------------- |
| Camera FPS         | >= 25                             | >= 25                               |
| LLM Latency        | < 2s (embedded), < 3s (LM Studio) | < 10s (embedded), < 15s (LM Studio) |
| Memory             | < 4GB                             | < 6GB                               |
| CPU (sustained)    | < 50%                             | < 70%                               |
| Detection accuracy | >= 70% for obvious states         | >= 70%                              |

## macOS Permissions

### Camera (Experiment 1, 2)
カメラへのアクセス許可が必要です。初回実行時にmacOSのダイアログが表示されます。

### Input Monitoring / Accessibility (Experiment 3)

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

## Models

| Model                     | Format      | Size   | Purpose                |
| ------------------------- | ----------- | ------ | ---------------------- |
| Qwen2.5-3B-Instruct       | GGUF Q4_K_M | ~2.0GB | Text LLM (llama.cpp)   |
| Qwen2.5-3B-Instruct-4bit  | MLX         | ~1.8GB | Text LLM (MLX)         |
| Qwen2-VL-2B-Instruct      | GGUF Q4_K_M | ~1.5GB | Vision LLM (llama.cpp) |
| Qwen2-VL-2B-Instruct-4bit | MLX         | ~1.5GB | Vision LLM (MLX)       |

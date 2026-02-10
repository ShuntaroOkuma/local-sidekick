# Local Sidekick PoC

Proof of Concept for Local Sidekick -- an always-on macOS observer that detects drowsiness, focus, and distraction using on-device camera analysis and PC usage monitoring with local LLMs.

## Overview

This PoC validates three core technical hypotheses:

1. **Experiment 1 (Embedded LLM)**: Camera face features extracted via MediaPipe can be classified by on-device LLMs (llama.cpp / MLX) into focused/drowsy/distracted states
2. **Experiment 2 (LM Studio)**: The same classification works via LM Studio's OpenAI-compatible API as an alternative backend
3. **Experiment 3 (PC Usage)**: OS-level metadata (active app, keyboard/mouse activity, idle time) can be analyzed by LLMs to detect focused/distracted/idle states

**Target environment**: Python / Apple Silicon M3-M4 (16-36GB RAM) / macOS

## Directory Structure

```
poc/
  pyproject.toml              # Dependencies (grouped by experiment)
  download_models.py          # Model download helper (Qwen2.5/Qwen2-VL)

  shared/
    __init__.py
    camera.py                 # Webcam + MediaPipe FaceMesh pipeline
    features.py               # Feature extraction (EAR, PERCLOS, head pose, blink, yawn)
    metrics.py                # Performance measurement (FPS, latency, CPU/RAM)
    prompts.py                # LLM prompt templates

  experiment1_embedded/       # Experiment 1: Embedded LLM
    __init__.py
    run_text_llama_cpp.py     # Features JSON -> llama-cpp-python
    run_text_mlx.py           # Features JSON -> mlx-lm
    run_vision_llama_cpp.py   # Camera frame -> llama-cpp-python (vision)
    run_vision_mlx.py         # Camera frame -> mlx-vlm (vision)

  experiment2_lmstudio/       # Experiment 2: LM Studio
    __init__.py
    run_text_lmstudio.py      # Features JSON -> LM Studio API
    run_vision_lmstudio.py    # Camera frame -> LM Studio Vision API

  experiment3_pcusage/        # Experiment 3: PC usage monitoring
    __init__.py
    monitor.py                # Data collection (app name, keyboard, mouse, idle)
    run_analysis.py           # Collected data -> LLM analysis
```

## Setup

### Prerequisites

- macOS with Apple Silicon (M3/M4, 16GB+ RAM)
- Python 3.11+
- LM Studio installed (for Experiment 2)

### Installation

```bash
cd poc/

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install all dependencies
pip install -e ".[all]"

# Download models (~7-8GB total)
python download_models.py
```

### Models

| Model | Format | Size | Purpose |
|-------|--------|------|---------|
| Qwen2.5-3B-Instruct | GGUF Q4_K_M | ~2.0GB | Text LLM (llama.cpp) |
| Qwen2.5-3B-Instruct-4bit | MLX | ~1.8GB | Text LLM (MLX) |
| Qwen2-VL-2B-Instruct | GGUF Q4_K_M | ~1.5GB | Vision LLM (llama.cpp) |
| Qwen2-VL-2B-Instruct-4bit | MLX | ~1.5GB | Vision LLM (MLX) |

### macOS Permissions

- **Camera**: Required for all camera experiments
- **Input Monitoring** (System Settings > Privacy & Security > Input Monitoring): Required for Experiment 3 (pynput keyboard/mouse event counting)

## Running Experiments

### Shared module verification

```bash
# Verify camera + FaceMesh pipeline (shows video for 10 seconds)
python -m shared.camera --show-video --duration 10

# Verify PC usage monitor (collects data for 30 seconds)
python -m experiment3_pcusage.monitor --duration 30
```

### Experiment 1: Embedded LLM

```bash
# Text mode: features JSON -> LLM
python -m experiment1_embedded.run_text_llama_cpp --duration 60 --interval 5
python -m experiment1_embedded.run_text_mlx --duration 60 --interval 5

# Vision mode: camera frame -> LLM (slower, longer intervals)
python -m experiment1_embedded.run_vision_llama_cpp --duration 120 --interval 15
python -m experiment1_embedded.run_vision_mlx --duration 120 --interval 15
```

### Experiment 2: LM Studio

**Prerequisite**: Load a compatible model in LM Studio first.

```bash
# Text mode
python -m experiment2_lmstudio.run_text_lmstudio --duration 60 --interval 5

# Vision mode
python -m experiment2_lmstudio.run_vision_lmstudio --duration 120 --interval 15
```

### Experiment 3: PC Usage Monitoring

```bash
python -m experiment3_pcusage.run_analysis --backend lmstudio --duration 300 --interval 30
```

Backend options: `lmstudio`, `llama_cpp`, `mlx`

## Success Criteria

### Experiment 1 - Embedded LLM

| Metric | Text Mode Target | Vision Mode Target |
|--------|-----------------|-------------------|
| Camera FPS (incl. feature extraction) | >= 25 FPS | >= 25 FPS |
| LLM Latency | < 2s | < 10s |
| Memory Usage | < 4GB | < 6GB |
| CPU Usage (sustained) | < 50% | < 70% |
| Classification Quality | >= 70% correct for obvious states | Same |

### Experiment 2 - LM Studio

| Metric | Target |
|--------|--------|
| LLM Latency (text) | < 3s |
| LLM Latency (vision) | < 15s |
| Quality vs. embedded | Comparable |
| Integration simplicity | Simpler than embedded |

### Experiment 3 - PC Usage

| Metric | Target |
|--------|--------|
| Collection overhead | < 1% CPU |
| Permission detection | Detects and guides required permissions |
| State classification | Correctly distinguishes idle/distracted/focused |

### Overall PoC Success

1. At least one of text or vision mode achieves practical latency + quality
2. LM Studio integration works as an alternative to embedded
3. PC usage monitoring runs stably for 5+ minutes
4. Memory stays under 6GB, allowing coexistence with normal work

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| MediaPipe not supported on macOS ARM | Fall back to `mediapipe-silicon` fork or Apple Vision Framework (PyObjC) |
| llama-cpp-python Metal compilation failure | Use pre-built wheel or CPU-only execution |
| Vision model too slow for practical use | Document text-features approach as recommended; limit vision to periodic deep analysis |
| pynput broken on macOS Sequoia | Detect permissions at startup; fall back to CGEventSource only |
| LM Studio not running / model not loaded | Connection check at startup with clear error message |

## Privacy Design

- **No content recording**: Only metadata is collected (app names, event counts, idle time)
- **No key logging**: Only keyboard event counts, never keystroke content
- **No screen capture**: Camera captures user's face only, never screen content
- **On-device processing**: Video frames are processed locally, never sent externally

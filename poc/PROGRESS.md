# PoC Implementation Progress

## Status Overview

| Task | Status | Owner |
|------|--------|-------|
| Project setup (pyproject.toml, dirs) | Done | foundation-dev |
| shared/camera.py | Done | foundation-dev |
| shared/features.py | Done | foundation-dev |
| shared/metrics.py | Done | foundation-dev |
| shared/prompts.py | Done | foundation-dev |
| download_models.py | Done | foundation-dev |
| Experiment 1: Text modes | Done | exp1-dev |
| Experiment 1: Vision modes | Done | exp1-dev |
| Experiment 2: LM Studio | Done | exp1-dev |
| Experiment 3: PC Usage | Done | exp23-dev |
| Code review: Shared modules | Done | reviewer |
| Code review: Experiments | Done | reviewer |
| README.md / PROGRESS.md | Done | reviewer |
| Fix blockers (model paths, merge) | Done | team-lead |

## Completed

### Project Setup (foundation-dev)
- `pyproject.toml` with grouped dependencies (core, llama, mlx, lmstudio, pcusage, download, all)
- Directory structure: `shared/`, `experiment1_embedded/`, `experiment2_lmstudio/`, `experiment3_pcusage/`
- All `__init__.py` files

### Shared Modules (foundation-dev)
- **camera.py**: `CameraCapture` with cv2 + MediaPipe FaceMesh (478 landmarks), `FrameResult` dataclass, base64 encoding
- **features.py**: EAR, MAR, head pose (solvePnP), `FeatureTracker` with PERCLOS + blink detection
- **metrics.py**: `MetricsCollector` with frame/LLM timing, CPU/memory, P95 stats
- **prompts.py**: Three prompt templates (text, vision, PC usage) with JSON response format

### Experiment 1 - Embedded LLM (exp1-dev)
- **run_text_llama_cpp.py**: Camera -> features -> llama-cpp-python (Qwen2.5-3B, Metal GPU)
- **run_text_mlx.py**: Camera -> features -> mlx-lm (Qwen2.5-3B-4bit, Apple Silicon)
- **run_vision_llama_cpp.py**: Camera frame -> base64 JPEG -> llama-cpp-python vision (Qwen2-VL-2B)
- **run_vision_mlx.py**: Camera frame -> PIL Image -> mlx-vlm (Qwen2-VL-2B-4bit)

### Experiment 2 - LM Studio (exp1-dev)
- **run_text_lmstudio.py**: Features -> LM Studio OpenAI-compatible API, connection check at startup
- **run_vision_lmstudio.py**: Camera frame -> LM Studio Vision API, data URI format

### Experiment 3 - PC Usage (exp23-dev)
- **monitor.py**: `PCUsageMonitor` with NSWorkspace, pynput, CGEventSource. Privacy-first design (only event counts).
- **run_analysis.py**: 3 backends (lmstudio/llama_cpp/mlx), 30s interval, results saved to JSON

### Code Review (reviewer)
- All shared modules reviewed: code quality PASS across all files
- All experiments reviewed: code quality PASS, 1 HIGH issue (vision chat_handler)
- Review files committed on poc/review branch

### Blocker Fixes (team-lead)
- Merged all 4 branches into poc/implementation
- Fixed model path mismatch: all scripts now use `poc/models/` (matching download_models.py output)
- Resolved exp2 duplicate (kept exp1-dev's implementation)
- Fixed exp3 run_analysis.py model subdirectory names

## Known Issues

### Resolved
- Model path mismatch between download_models.py and experiment scripts -> Fixed
- Experiment 2 duplicate implementations on two branches -> Resolved (kept exp1-dev's)
- exp3 model subdirectory names didn't match download output -> Fixed

### Remaining (non-blocking for PoC)
- Vision llama.cpp chat_handler: Falls back to None if CLIP model not found (warns but continues)
- download_models.py doesn't include CLIP/mmproj model for Qwen2-VL vision (user may need to download separately)
- Mouse move events in monitor.py may generate high counts (consider rate-limiting for production)
- PERCLOS rates computed from total since start, not windowed (early readings dominate)

## Ready for Manual Testing

All implementation and review tasks are complete. The PoC is ready for manual testing per the test protocol in poc-plan.md.

### Setup Steps
```bash
cd poc/
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"
python download_models.py
```

### Test Execution
See poc-plan.md "テストプロトコル（手動検証）" section.

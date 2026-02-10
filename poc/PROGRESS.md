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
| Experiment 1: Text modes | Pending | exp1-dev |
| Experiment 1: Vision modes | Pending | exp1-dev |
| Experiment 2: LM Studio | Pending | exp23-dev |
| Experiment 3: PC Usage | Pending | exp23-dev |
| Code review: Shared modules | Pending | reviewer |
| Code review: Experiments | Pending | reviewer |
| README.md / PROGRESS.md | Done | foundation-dev |

## Completed

### Project Setup
- Created `pyproject.toml` with grouped dependencies (core, llama, mlx, lmstudio, pcusage, download, all)
- Created directory structure: `shared/`, `experiment1_embedded/`, `experiment2_lmstudio/`, `experiment3_pcusage/`
- Created all `__init__.py` files
- Created README.md with quick start guide

### Shared Modules
- **camera.py**: `CameraCapture` class with cv2 + MediaPipe FaceMesh (478 landmarks with iris), `read_frame()` returns `FrameResult`, `get_frame_as_base64()` for vision models, standalone test via `python -m shared.camera`
- **features.py**: `extract_frame_features()` computes EAR (both eyes), MAR, head pose (pitch/yaw/roll via solvePnP). `FeatureTracker` class provides sliding-window PERCLOS and blink detection. All frozen dataclasses with JSON serialization.
- **metrics.py**: `MetricsCollector` with context managers `measure_frame()` and `measure_llm()`, tracks FPS, latency (avg/P95), CPU%, memory. `MetricsSummary` with formatted report.
- **prompts.py**: Three prompt templates (text features, vision image, PC usage) with system+user prompt pairs. All enforce JSON-only response format.

### Download Models
- **download_models.py**: Downloads 4 models (2 GGUF + 2 MLX) from Hugging Face Hub. Supports `--text-only` and `--check` flags. Helper functions `get_gguf_model_path()` and `get_mlx_model_path()` for experiments to locate models.

## Notes

- All work happens in `poc/` subdirectory
- Python 3.11+ required
- Apple Silicon (M3-M4) target environment
- Foundation modules are ready for experiment agents to build on

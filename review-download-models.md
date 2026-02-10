# Code Review: download_models.py

**Branch**: `poc/foundation`
**Commit**: `33e4f86` - feat: implement download_models.py for GGUF and MLX model management
**Reviewer**: reviewer
**Date**: 2026-02-10

## poc/download_models.py (246 lines)

**Status**: PASS

Checklist:
- [x] Immutability: GGUFModel and MLXModel are frozen dataclasses; model lists are tuples
- [x] Error handling: ImportError for optional huggingface-hub, skip-if-exists logic, file existence checks
- [x] Type hints: All functions annotated
- [x] File size: 246 lines (under 800)
- [x] Function size: All under 50 lines
- [x] No hardcoded secrets
- [x] Adherence to poc-plan: Correct model names (Qwen2.5-3B Q4_K_M, Qwen2-VL-2B Q4_K_M), correct sizes, both GGUF and MLX formats

Positives:
- Frozen dataclasses for model definitions
- Skip-if-exists logic prevents redundant downloads
- `--check` mode for verifying download status without downloading
- `--text-only` flag to skip larger vision models
- `get_gguf_model_path()` and `get_mlx_model_path()` lookup helpers
- Clean CLI with argparse

Notes:
- MODELS_DIR uses `Path(__file__).parent / "models"` which places models inside the poc/ directory. This could make the project directory large (~7-8GB). Consider using `~/.cache/local-sidekick/models/` instead (which is what the experiment scripts expect via DEFAULT_MODEL_PATH)

Issue (MEDIUM): **Model path mismatch with experiment scripts.** The experiment scripts (e.g., `run_text_llama_cpp.py`) expect models at `~/.cache/local-sidekick/models/`, but `download_models.py` downloads to `poc/models/`. Either the download script or the experiment defaults need to be aligned.

Issue (LOW): `check_models()` has a somewhat complex conditional for checking directory existence (`path.exists() and (path.is_file() or any(path.iterdir()) if path.is_dir() else True)`). This could be simplified but works correctly.

## Summary

| Category | Result |
|----------|--------|
| Code quality | PASS |
| Immutability | PASS |
| Error handling | PASS |
| Security | PASS |
| Plan adherence | PASS |
| Model path compatibility | **MEDIUM issue** - path mismatch with experiments |
| Overall | PASS with one medium issue |

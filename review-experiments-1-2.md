# Code Review: Experiments 1 & 2

**Branch**: `poc/experiment1`
**Commit**: `ec2fb4e` - feat: implement experiment 1 (embedded LLM) and experiment 2 (LM Studio) scripts
**Reviewer**: reviewer
**Date**: 2026-02-10

## Files Reviewed

### 1. poc/experiment1_embedded/run_text_llama_cpp.py (172 lines)

**Status**: PASS

Checklist:
- [x] Immutability: No mutation of shared state (should_run list pattern is intentional for signal handlers)
- [x] Error handling: Model file existence check, JSON parse error handling, graceful shutdown via signal
- [x] Type hints: All functions annotated
- [x] File size: 172 lines (well under 800)
- [x] Function size: All under 50 lines
- [x] No hardcoded secrets
- [x] Resource cleanup: camera.stop() in finally block
- [x] Privacy: No frame storage or recording
- [x] Adherence to poc-plan: llama-cpp-python, Metal GPU (n_gpu_layers=-1), 5s interval, 60s duration, Qwen2.5-3B

Issue (MEDIUM): No error handling around `camera.start()`. If camera access fails, the exception propagates uncaught.

### 2. poc/experiment1_embedded/run_text_mlx.py (171 lines)

**Status**: PASS

Checklist:
- [x] Immutability
- [x] Error handling: JSON parse, graceful shutdown
- [x] Type hints: Present (note: `load_model` returns untyped `tuple`)
- [x] File size: 171 lines
- [x] Function size: All under 50 lines
- [x] No hardcoded secrets
- [x] Resource cleanup: camera.stop() in finally
- [x] Privacy: No frame storage
- [x] Adherence to poc-plan: mlx-lm, Qwen2.5-3B-4bit, apply_chat_template with fallback

Issue (LOW): `load_model` return type is bare `tuple` -- could be `tuple[Any, Any]` for clarity.
Issue (MEDIUM): Same camera.start() error handling gap.

### 3. poc/experiment1_embedded/run_vision_llama_cpp.py (202 lines)

**Status**: PASS with one HIGH issue

Checklist:
- [x] Immutability
- [x] Error handling: Model file check, null base64 check, JSON parse
- [x] Type hints: Present
- [x] File size: 202 lines
- [x] Function size: All under 50 lines
- [x] No hardcoded secrets
- [x] Resource cleanup: camera.stop() in finally
- [x] Privacy: base64 images only in memory, never stored
- [x] Adherence to poc-plan: Qwen2-VL-2B, 15s interval, 120s duration

Issue (HIGH): `chat_handler=None` in `load_model()` (line ~87). llama-cpp-python requires a chat handler for multimodal/vision models (e.g., `Llava15ChatHandler` or similar). Without it, the vision inference via `create_chat_completion` with image content will likely fail at runtime. Recommend using `llama_cpp.llama_chat_format.Llava15ChatHandler` or the appropriate handler for Qwen2-VL.

Issue (MEDIUM): Same camera.start() error handling gap.

### 4. poc/experiment1_embedded/run_vision_mlx.py (176 lines)

**Status**: PASS

Checklist:
- [x] Immutability
- [x] Error handling: Null frame check, JSON parse
- [x] Type hints: Present (same bare tuple note)
- [x] File size: 176 lines
- [x] Function size: All under 50 lines
- [x] No hardcoded secrets
- [x] Resource cleanup: camera.stop() in finally
- [x] Privacy: PIL images only in memory
- [x] Adherence to poc-plan: mlx-vlm, Qwen2-VL-2B-4bit

Note: `from mlx_vlm import generate` inside function body (lazy import) -- acceptable for optional dependency, but adds per-call overhead. Consider caching or moving to module-level with try/except.

Issue (MEDIUM): Same camera.start() error handling gap.

### 5. poc/experiment2_lmstudio/run_text_lmstudio.py (179 lines)

**Status**: PASS

Checklist:
- [x] Immutability
- [x] Error handling: Excellent -- connection check at startup, APIConnectionError and APIError caught in main loop
- [x] Type hints: Present
- [x] File size: 179 lines
- [x] Function size: All under 50 lines
- [x] No hardcoded secrets (api_key="lm-studio" is LM Studio convention)
- [x] Resource cleanup: camera.stop() in finally
- [x] Privacy: No frame storage
- [x] Adherence to poc-plan: OpenAI client, localhost:1234, connection check at startup

Best error handling of all 6 files. Good pattern to follow.

Issue (LOW): `model="default"` may not work with all LM Studio versions. Consider using first model from the list returned by check.

### 6. poc/experiment2_lmstudio/run_vision_lmstudio.py (193 lines)

**Status**: PASS

Checklist:
- [x] Immutability
- [x] Error handling: Same excellent pattern as text variant
- [x] Type hints: Present
- [x] File size: 193 lines
- [x] Function size: All under 50 lines
- [x] No hardcoded secrets
- [x] Resource cleanup: camera.stop() in finally
- [x] Privacy: base64 images in memory only
- [x] Adherence to poc-plan: data URI format, vision-capable model check messaging

## Cross-Cutting Observations

### Code Duplication (INFO)
The main loop pattern is nearly identical across all 6 files (~40 lines each). For a PoC this is acceptable -- it keeps each script self-contained and independently runnable. In production, this would warrant extracting a common runner.

### Consistent Patterns (POSITIVE)
- All files follow the same structure: imports, constants, parse_args, load_model, run_inference, shutdown_handler, main
- Consistent output format across all experiments for easy comparison
- All use MetricsCollector consistently

### Missing camera.start() Error Handling (MEDIUM)
All 6 files lack try/except around `camera.start()`. If the camera is unavailable (permissions denied, in use by another app), the script will crash with an unhelpful error. Recommend wrapping in try/except with a user-friendly message.

## Summary

| File | Lines | Status | Issues |
|------|-------|--------|--------|
| run_text_llama_cpp.py | 172 | PASS | camera.start() handling (M) |
| run_text_mlx.py | 171 | PASS | camera.start() handling (M), bare tuple type (L) |
| run_vision_llama_cpp.py | 202 | PASS* | **chat_handler=None (H)**, camera.start() handling (M) |
| run_vision_mlx.py | 176 | PASS | camera.start() handling (M), lazy import overhead (L) |
| run_text_lmstudio.py | 179 | PASS | model="default" (L) |
| run_vision_lmstudio.py | 193 | PASS | model="default" (L) |

**HIGH priority**: Fix `chat_handler=None` in `run_vision_llama_cpp.py` -- this will likely cause runtime failures.

**MEDIUM priority**: Add camera.start() error handling across all files (can be done as a batch fix).

**Overall**: Well-structured PoC code. Consistent patterns, proper resource cleanup, good adherence to the plan. The LM Studio variants have the best error handling and could serve as a template.

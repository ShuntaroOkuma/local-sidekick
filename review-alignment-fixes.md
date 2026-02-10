# Code Review: Alignment Fixes

**Date**: 2026-02-10

## Experiment 1 & 2 Fixes (poc/experiment1)

**Commit**: `feea76d` - feat: align experiment scripts with shared module APIs

### Changes Reviewed

All 6 experiment scripts were updated to align with the shared module interfaces:

1. **CameraCapture**: Now uses `with CameraCapture() as camera:` context manager instead of manual `start()/stop()`. FIXED.
2. **read_frame()**: Now handles `FrameResult` object properly (`frame_result.landmarks`, `frame_result.timestamp`). FIXED.
3. **FeatureTracker**: Now calls `extract_frame_features(landmarks, timestamp)` first, then passes `FrameFeatures` to `tracker.update()`. FIXED.
4. **Prompts**: Now imports `TEXT_SYSTEM_PROMPT`, `format_text_prompt`, `VISION_SYSTEM_PROMPT`, `VISION_USER_PROMPT` correctly. FIXED.
5. **MetricsCollector**: Now uses `MetricsCollector()` (no args), `metrics.start()`, `metrics.measure_frame()` and `metrics.measure_llm()` context managers, `metrics.get_summary()` returns MetricsSummary. FIXED.
6. **Vision chat_handler**: Now uses `Llava15ChatHandler(clip_model_path=...)` when clip model file exists, falls back to None with warning. FIXED.

**Status**: All CRITICAL and HIGH issues from previous review are resolved.

## Experiment 2 & 3 Fixes (poc/experiment23)

**Commit**: `8bc1bfb` - refactor: integrate shared prompts and metrics into run_analysis.py
**Commit**: `e1360e4` - feat: implement Experiment 2 LM Studio variants (text + vision)

### Changes Reviewed

1. **run_analysis.py**: Refactored to import `PC_USAGE_SYSTEM_PROMPT`, `format_pc_usage_prompt` from shared/prompts.py and `MetricsCollector` from shared/metrics.py. Uses shared modules instead of duplicating prompt text. FIXED.
2. **LM Studio scripts**: New implementations for Experiment 2 on the exp23 branch, properly using shared module APIs. PASS.

### Remaining Issue (MEDIUM)

Model path mismatch between download_models.py and experiment scripts still exists. The exp1 scripts expect models at `~/.cache/local-sidekick/models/` while download_models.py saves to `poc/models/`. This hasn't been addressed yet but is a configuration issue, not a code quality issue -- users can specify `--model-path` to override.

## Summary

| Issue | Severity | Status |
|-------|----------|--------|
| Interface mismatch (shared vs experiments) | CRITICAL | **RESOLVED** |
| Vision chat_handler=None | HIGH | **RESOLVED** |
| Model path mismatch | MEDIUM | Open (workaround: --model-path flag) |
| camera.start() error handling | MEDIUM | **RESOLVED** (context manager handles it) |

All blocking issues have been resolved. The codebase is now internally consistent and should work end-to-end (assuming models are downloaded to the correct paths).

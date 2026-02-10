# Code Review: Experiment 3 - PC Usage Monitoring

**Branch**: `poc/experiment23`
**Commit**: `046e1e7` - feat: implement download_models.py for model download helper
**Reviewer**: reviewer
**Date**: 2026-02-10

## Files Reviewed

### 1. poc/experiment3_pcusage/monitor.py (392 lines)

**Status**: PASS

Checklist:
- [x] Immutability: UsageSnapshot is frozen dataclass
- [x] Error handling: Permission checks with clear guidance, graceful fallbacks for pynput/NSWorkspace/CGEvent failures
- [x] Type hints: All public functions annotated
- [x] File size: 392 lines (under 800)
- [x] Function size: All under 50 lines
- [x] No hardcoded secrets
- [x] Resource cleanup: stop() method cleans up listeners in finally-equivalent pattern
- [x] **Privacy: PASS** - Only counts keyboard/mouse events, never records content. Explicit docstring: "Never records keyboard/mouse content - only event counts"
- [x] Adherence to poc-plan: NSWorkspace for active app, pynput for event counting, CGEventSource for idle time, permission detection and guidance

Positives:
- **Excellent privacy design**: `_MutableCounters` only increments integer counters, never stores key/mouse content
- **Thread safety**: Lock-protected counters for concurrent listener threads
- **Permission detection**: `check_permissions()` tests each API independently and `print_permission_guidance()` gives macOS-specific instructions
- **Graceful degradation**: If pynput fails, prints warning but continues monitoring (app name + idle still work)
- **Immutable snapshots**: `UsageSnapshot` is a frozen dataclass returned from `take_snapshot()`
- **Sliding window**: App history tracked with deque and time-based pruning
- **Standalone test**: `python -m experiment3_pcusage.monitor --duration 30` works as specified in poc-plan

Notes:
- `_MutableCounters` is the one mutable dataclass, correctly isolated with thread lock. Internal use only. Acceptable.
- Mouse move events may generate extremely high counts (hundreds per second). Consider rate-limiting or sampling mouse moves to avoid noise in events_per_min. Not a blocker for PoC.
- `keyboard_events_per_min` and `mouse_events_per_min` are computed from total since start, not windowed. This means early readings dominate. Consider windowed rates for more representative readings. Not a blocker.

### 2. poc/experiment3_pcusage/run_analysis.py (495 lines)

**Status**: PASS with notes

Checklist:
- [x] Immutability: LLMResult is frozen dataclass
- [x] Error handling: Backend pre-flight checks (LM Studio connection, model file existence), per-analysis try/except, markdown code block stripping in JSON parsing
- [x] Type hints: All public functions annotated
- [x] File size: 495 lines (approaching 500 -- watch this if adding more)
- [x] Function size: All under 50 lines (largest is `run_analysis` at ~48 lines in the try block)
- [x] No hardcoded secrets (api_key="lm-studio" is convention)
- [x] Resource cleanup: monitor.stop() in finally block
- [x] Privacy: Only sends metadata to LLM (app names, event counts, idle time)
- [x] Adherence to poc-plan: Three backends (lmstudio, llama_cpp, mlx), 30s interval, 300s duration, --backend flag

Positives:
- **Three backends** with clean dispatch via BACKENDS dict
- **Model caching**: `_llama_model_cache` and `_mlx_model_cache` prevent reloading per call
- **JSON parsing robustness**: Handles markdown code block wrapping (`\`\`\``) that LLMs sometimes add
- **Pre-flight checks**: Verifies LM Studio connection, model file existence before starting
- **Results saved to file**: JSON output in `poc/results/` with timestamped filename
- **Summary report**: State distribution and latency percentiles at end
- **Clean prompt design**: Own system/user prompts (doesn't depend on shared/prompts.py -- avoids the interface mismatch issue)

Issues:

Issue (MEDIUM): **Model path references differ from download_models.py.** The llama.cpp backend looks for model at `models/qwen2.5-3b-instruct-gguf/qwen2.5-3b-instruct-q4_k_m.gguf`, but `download_models.py` saves to `models/qwen2.5-3b-instruct-q4_k_m.gguf` (flat, no subdirectory). Similarly, MLX backend expects `models/qwen2.5-3b-instruct-mlx/` but download_models.py saves to `models/qwen2.5-3b-instruct-4bit/`. These mismatches will cause "model not found" errors.

Specific mismatches:
- llama.cpp expects: `models/qwen2.5-3b-instruct-gguf/qwen2.5-3b-instruct-q4_k_m.gguf`
- download_models.py saves: `models/qwen2.5-3b-instruct-q4_k_m.gguf`
- MLX expects: `models/qwen2.5-3b-instruct-mlx/`
- download_models.py saves: `models/qwen2.5-3b-instruct-4bit/`

Issue (LOW): **Mutable module-level caches** (`_llama_model_cache`, `_mlx_model_cache`) are mutable dicts. This is acceptable for PoC caching but doesn't follow the immutability rule strictly. A frozen approach would require a different caching strategy.

Issue (LOW): `history` list mutation in `run_analysis()` -- `history = history[-20:]` creates a new list (good) but `history.append(snapshot)` mutates. For PoC this is fine.

## Summary

| File | Lines | Status | Key Issues |
|------|-------|--------|-----------|
| monitor.py | 392 | **PASS** | None (excellent privacy design) |
| run_analysis.py | 495 | **PASS** | Model path mismatch (M) |

### Overall Assessment

Experiment 3 code is high quality. The privacy design in monitor.py is exemplary -- thread-safe counters that never store content, permission detection with clear macOS guidance, and graceful degradation when permissions are missing.

The main risk is the model path mismatch between run_analysis.py and download_models.py which will cause runtime errors when using llama_cpp or mlx backends.

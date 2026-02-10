# Code Review: Shared Modules

**Branch**: `poc/foundation`
**Commit**: `c12367b` - feat: implement shared modules (camera, features, metrics, prompts)
**Reviewer**: reviewer
**Date**: 2026-02-10

## CRITICAL: Interface Mismatch with Experiment Scripts

The shared modules and experiment scripts (on `poc/experiment1`) were developed independently and have **incompatible interfaces**. All 6 experiment scripts will fail at runtime with ImportError or AttributeError.

### Mismatch Summary

| Component | Experiment Scripts Expect | Shared Module Provides |
|-----------|--------------------------|----------------------|
| CameraCapture.start() | `camera.start()` | `camera.open()` |
| CameraCapture.stop() | `camera.stop()` | `camera.close()` |
| CameraCapture.read_frame() | Returns `(frame, landmarks)` tuple | Returns `FrameResult` dataclass |
| FeatureTracker.update() | Takes raw `landmarks` | Takes `FrameFeatures` object |
| FeatureTracker.get_no_face_features() | Expected method | Does not exist |
| build_text_prompt() | `from shared.prompts import build_text_prompt` | Function is named `format_text_prompt` |
| build_vision_prompt() | `from shared.prompts import build_vision_prompt` | Does not exist (only `VISION_USER_PROMPT` constant) |
| MetricsCollector() | `MetricsCollector(experiment_name=...)` | `MetricsCollector(max_samples=...)` |
| MetricsCollector.record_frame() | Takes `frame_time` argument | Takes no arguments |
| MetricsCollector.record_llm_call() | Expected method | Does not exist (use `measure_llm()` context manager) |
| MetricsCollector.current_fps | Expected property | Does not exist |
| MetricsCollector.get_summary() | Returns `dict` | Returns `MetricsSummary` object |

### Recommended Fix

Either the shared modules or the experiment scripts need to be updated. My recommendation:

**Option A** (Preferred): Update the shared modules to match experiment script expectations. This is better because the experiment scripts follow a simpler, more intuitive API. Specific changes needed:
1. Add `start()`/`stop()` aliases for `open()`/`close()` in CameraCapture
2. Add a `read_frame_tuple()` method or modify `read_frame()` to return `(frame, landmarks)`
3. Add `build_text_prompt()` and `build_vision_prompt()` functions to prompts.py
4. Add `experiment_name` param, `record_frame(time)`, `record_llm_call(time)`, `current_fps` to MetricsCollector
5. Make FeatureTracker.update() accept raw landmarks (call extract_frame_features internally)
6. Add `get_no_face_features()` to FeatureTracker

**Option B**: Update the experiment scripts to use the shared module API as-is. This means refactoring all 6 files.

---

## File Reviews (Code Quality)

### 1. poc/shared/camera.py (266 lines)

**Status**: PASS (code quality is high)

Checklist:
- [x] Immutability: Landmark and FrameResult are frozen dataclasses
- [x] Error handling: Excellent -- RuntimeError on camera open failure with macOS-specific guidance, RuntimeError on frame capture failure
- [x] Type hints: All functions annotated
- [x] File size: 266 lines (under 800)
- [x] Function size: All under 50 lines
- [x] No hardcoded secrets
- [x] Resource cleanup: Context manager support (__enter__/__exit__), explicit close()
- [x] Privacy: No frame storage; base64 is in-memory only
- [x] Adherence to poc-plan: 640x480, refine_landmarks=True (478 points), FaceMesh with correct settings
- [x] Standalone test: `python -m shared.camera --show-video --duration 10` implemented correctly

Positives:
- Frozen dataclasses for Landmark and FrameResult (true immutability)
- Context manager pattern (with statement support)
- Setting `rgb_frame.flags.writeable = False` for MediaPipe performance optimization
- Good error messages with macOS permission guidance
- Visualization helper `_draw_landmarks_on_frame` copies frame before drawing

### 2. poc/shared/features.py (444 lines)

**Status**: PASS (code quality is high)

Checklist:
- [x] Immutability: HeadPose, FrameFeatures, TrackerSnapshot all frozen dataclasses
- [x] Error handling: Division by zero guards in EAR/MAR, solvePnP failure handling
- [x] Type hints: All functions annotated
- [x] File size: 444 lines (under 800)
- [x] Function size: All under 50 lines
- [x] No hardcoded secrets
- [x] Adherence to poc-plan: Correct landmark indices for EAR/MAR, thresholds match plan, PERCLOS sliding window

Positives:
- EAR landmark indices match poc-plan exactly: right [33,160,158,133,153,144], left [362,385,387,263,380,373]
- Thresholds match plan: EAR < 0.20, PERCLOS > 0.15, MAR > 0.6
- 60-second sliding window for PERCLOS as specified
- Head pose via cv2.solvePnP with 6 key points
- Blink detection with proper open/close state machine
- _BlinkState uses immutable replacement pattern in _detect_blink (creates new _BlinkState instead of mutating)

Note: _BlinkState is a mutable dataclass (not frozen) but is only used internally and replaced via new instance creation -- acceptable.

### 3. poc/shared/metrics.py (213 lines)

**Status**: PASS (code quality is high)

Checklist:
- [x] Immutability: MetricsSummary is frozen dataclass
- [x] Error handling: psutil.Error caught in CPU sampling, division by zero guards
- [x] Type hints: All functions annotated
- [x] File size: 213 lines (under 800)
- [x] Function size: All under 50 lines
- [x] No hardcoded secrets
- [x] Adherence to poc-plan: FPS, frame time, LLM latency (avg/P95), CPU%, memory MB

Positives:
- Context manager pattern for timing (`measure_frame()`, `measure_llm()`)
- Bounded deque (maxlen=10000) prevents unbounded memory growth
- P95 percentile calculation
- Good `print_report()` method for quick visual inspection

### 4. poc/shared/prompts.py (123 lines)

**Status**: PASS (code quality is high)

Checklist:
- [x] Immutability: Only string constants and pure functions
- [x] Error handling: N/A (string formatting)
- [x] Type hints: All functions annotated
- [x] File size: 123 lines (under 800)
- [x] Function size: All under 50 lines
- [x] No hardcoded secrets
- [x] Privacy: Prompts correctly avoid requesting content recording
- [x] Adherence to poc-plan: Three prompt types (text, vision, PC usage), JSON response format

Positives:
- Clear classification rules in prompts matching poc-plan states
- Proper JSON response format specification
- "away" state handling for no-face/no-person scenarios
- PC usage prompt correctly identifies key indicators

Note: Missing `build_text_prompt()` and `build_vision_prompt()` wrapper functions that experiments expect.

## Overall Summary

| File | Lines | Code Quality | Interface Compatible |
|------|-------|-------------|---------------------|
| camera.py | 266 | PASS | NO - method names differ |
| features.py | 444 | PASS | NO - expects FrameFeatures, not landmarks |
| metrics.py | 213 | PASS | NO - different constructor/methods |
| prompts.py | 123 | PASS | NO - different function names |

**Code quality**: Excellent across all 4 files. Frozen dataclasses, proper error handling, good type hints, correct adherence to poc-plan specifications.

**CRITICAL BLOCKER**: Interface mismatch between shared modules and experiment scripts. Must be resolved before any experiment can run.

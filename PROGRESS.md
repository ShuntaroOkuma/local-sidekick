# Local Sidekick PoC - Progress Tracker

## Task Status

| # | Task | Owner | Status | Blocked By | Notes |
|---|------|-------|--------|------------|-------|
| 1 | Project setup: pyproject.toml, directory structure | foundation-dev | **Complete** | - | Reviewed: PASS |
| 2 | shared/camera.py - Camera + FaceMesh pipeline | foundation-dev | **Complete** | - | Reviewed: PASS |
| 3 | shared/features.py - Feature extraction | foundation-dev | **Complete** | - | Reviewed: PASS |
| 4 | shared/metrics.py and shared/prompts.py | foundation-dev | **Complete** | - | Reviewed: PASS |
| 5 | download_models.py - Model download helper | foundation-dev | **Complete** | - | Reviewed: PASS |
| 6 | Experiment 1: Text mode (llama.cpp + MLX) | exp1-dev | **Complete** | - | Reviewed: PASS |
| 7 | Experiment 1: Vision mode (llama.cpp + MLX) | exp1-dev | **Complete** | - | Reviewed: PASS (chat_handler fixed) |
| 8 | Experiment 2: LM Studio (text + vision) | exp1-dev/exp23-dev | **Complete** | - | Reviewed: PASS |
| 9 | Experiment 3: PC usage monitoring + analysis | exp23-dev | **Complete** | - | Reviewed: PASS |
| 10 | README.md and PROGRESS.md | reviewer | **Complete** | - | |
| 11 | Code review: Shared modules | reviewer | **Complete** | - | All issues resolved |
| 12 | Code review: All experiments | reviewer | **Complete** | - | All issues resolved |

## Per-Experiment Status

### Shared Modules
- **camera.py**: Complete, reviewed PASS (266 lines) -- CameraCapture with context manager, FaceMesh 478 landmarks
- **features.py**: Complete, reviewed PASS (444 lines) -- EAR, PERCLOS, MAR, head pose, blink detection
- **metrics.py**: Complete, reviewed PASS (213 lines) -- FPS, frame time, LLM latency, CPU/memory
- **prompts.py**: Complete, reviewed PASS (123 lines) -- Text, vision, PC usage prompt templates

### Experiment 1: Embedded LLM
- **run_text_llama_cpp.py**: Complete, reviewed PASS (aligned with shared modules)
- **run_text_mlx.py**: Complete, reviewed PASS (aligned with shared modules)
- **run_vision_llama_cpp.py**: Complete, reviewed PASS (Llava15ChatHandler fixed)
- **run_vision_mlx.py**: Complete, reviewed PASS (aligned with shared modules)

### Experiment 2: LM Studio
- **run_text_lmstudio.py**: Complete, reviewed PASS (on both exp1 and exp23 branches)
- **run_vision_lmstudio.py**: Complete, reviewed PASS (on both exp1 and exp23 branches)

### Experiment 3: PC Usage
- **monitor.py**: Complete, reviewed PASS (392 lines) -- Excellent privacy design
- **run_analysis.py**: Complete, reviewed PASS (refactored to use shared modules)

## Code Reviews

| Review | Files | Status | Link |
|--------|-------|--------|------|
| Foundation setup | pyproject.toml, __init__.py, docs | **PASS** | [review-foundation-setup.md](review-foundation-setup.md) |
| Shared modules | camera.py, features.py, metrics.py, prompts.py | **PASS** | [review-shared-modules.md](review-shared-modules.md) |
| Experiments 1 & 2 | 6 experiment scripts | **PASS** | [review-experiments-1-2.md](review-experiments-1-2.md) |
| download_models.py | download helper | **PASS** | [review-download-models.md](review-download-models.md) |
| Experiment 3 | monitor.py, run_analysis.py | **PASS** | [review-experiment3.md](review-experiment3.md) |
| Alignment fixes | All experiment scripts | **PASS** | [review-alignment-fixes.md](review-alignment-fixes.md) |

## Known Issues (Non-Blocking)

### MEDIUM: Model Path Mismatch
- download_models.py saves to `poc/models/` (relative)
- Experiment 1 scripts default to `~/.cache/local-sidekick/models/`
- Experiment 3 expects different subdirectory names
- **Workaround**: Use `--model-path` flag when running experiments
- **Status**: Non-blocking, can be fixed before manual testing

## Resolved Issues

| Issue | Severity | Resolution |
|-------|----------|------------|
| Interface mismatch (shared vs experiments) | CRITICAL | exp1-dev updated all 6 scripts to use shared module APIs |
| Vision chat_handler=None | HIGH | Fixed to use Llava15ChatHandler |
| camera.start() error handling | MEDIUM | Resolved by switching to CameraCapture context manager |
| Shared prompt/metrics not used in exp3 | MEDIUM | exp23-dev refactored run_analysis.py |

## Lessons Learned

- **Parallel independent development** of shared modules and experiment scripts led to interface mismatches. Define interfaces (type stubs or protocol classes) before parallel implementation.
- **Frozen dataclasses** used throughout the codebase provide good immutability guarantees.
- **Privacy-by-design** in monitor.py (count-only, no content) is an exemplary pattern for the full product.

## Key Milestones

| Milestone | Target | Actual | Status |
|-----------|--------|--------|--------|
| Project setup complete | - | 2026-02-10 | **Done** |
| Shared modules complete | - | 2026-02-10 | **Done** |
| Experiment 1 code complete | - | 2026-02-10 | **Done** |
| Experiment 2 code complete | - | 2026-02-10 | **Done** |
| Experiment 3 code complete | - | 2026-02-10 | **Done** |
| Interface alignment complete | - | 2026-02-10 | **Done** |
| All code reviews complete | - | 2026-02-10 | **Done** |
| Manual testing | - | - | Ready to start |

---

_Last updated: 2026-02-10_

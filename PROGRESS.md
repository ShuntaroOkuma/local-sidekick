# Local Sidekick PoC - Progress Tracker

## Task Status

| # | Task | Owner | Status | Blocked By | Notes |
|---|------|-------|--------|------------|-------|
| 1 | Project setup: pyproject.toml, directory structure | foundation-dev | **Complete** | - | Reviewed: PASS |
| 2 | shared/camera.py - Camera + FaceMesh pipeline | foundation-dev | **Complete** | - | Reviewed: PASS (interface mismatch) |
| 3 | shared/features.py - Feature extraction | foundation-dev | **Complete** | - | Reviewed: PASS (interface mismatch) |
| 4 | shared/metrics.py and shared/prompts.py | foundation-dev | **Complete** | - | Reviewed: PASS (interface mismatch) |
| 5 | download_models.py - Model download helper | foundation-dev | **Complete** | - | Reviewed: PASS (path mismatch) |
| 6 | Experiment 1: Text mode (llama.cpp + MLX) | exp1-dev | **Complete** | - | Reviewed: PASS |
| 7 | Experiment 1: Vision mode (llama.cpp + MLX) | exp1-dev | **Complete** | - | Reviewed: PASS (chat_handler HIGH) |
| 8 | Experiment 2: LM Studio (text + vision) | exp1-dev | **Complete** | - | Reviewed: PASS |
| 9 | Experiment 3: PC usage monitoring + analysis | exp23-dev | **Complete** | - | Reviewed: PASS (path mismatch) |
| 10 | README.md and PROGRESS.md | reviewer | **Complete** | - | |
| 11 | Code review: Shared modules | reviewer | **Complete** | - | CRITICAL: interface mismatch |
| 12 | Code review: All experiments | reviewer | **In Progress** | - | Exp 1/2/3 reviewed; awaiting fixes |

## Per-Experiment Status

### Shared Modules
- **camera.py**: Complete, reviewed PASS (266 lines)
- **features.py**: Complete, reviewed PASS (444 lines)
- **metrics.py**: Complete, reviewed PASS (213 lines)
- **prompts.py**: Complete, reviewed PASS (123 lines)

### Experiment 1: Embedded LLM
- **run_text_llama_cpp.py**: Complete, reviewed PASS (172 lines)
- **run_text_mlx.py**: Complete, reviewed PASS (171 lines)
- **run_vision_llama_cpp.py**: Complete, reviewed PASS* (202 lines) -- HIGH: chat_handler=None
- **run_vision_mlx.py**: Complete, reviewed PASS (176 lines)

### Experiment 2: LM Studio
- **run_text_lmstudio.py**: Complete, reviewed PASS (179 lines)
- **run_vision_lmstudio.py**: Complete, reviewed PASS (193 lines)

### Experiment 3: PC Usage
- **monitor.py**: Complete, reviewed PASS (392 lines) -- Excellent privacy design
- **run_analysis.py**: Complete, reviewed PASS (495 lines)

## Code Reviews

| Review | Files | Status | Link |
|--------|-------|--------|------|
| Foundation setup | pyproject.toml, __init__.py, docs | **PASS** | [review-foundation-setup.md](review-foundation-setup.md) |
| Shared modules | camera.py, features.py, metrics.py, prompts.py | **PASS** (CRITICAL mismatch) | [review-shared-modules.md](review-shared-modules.md) |
| Experiments 1 & 2 | 6 experiment scripts | **PASS** (1 HIGH) | [review-experiments-1-2.md](review-experiments-1-2.md) |
| download_models.py | download helper | **PASS** (1 MEDIUM) | [review-download-models.md](review-download-models.md) |
| Experiment 3 | monitor.py, run_analysis.py | **PASS** (1 MEDIUM) | [review-experiment3.md](review-experiment3.md) |

## Known Issues and Blockers

### CRITICAL: Interface Mismatch (shared modules vs experiment scripts)
The shared modules (camera, features, metrics, prompts) and experiment scripts were developed independently with incompatible interfaces. All experiment scripts will fail at runtime. Key mismatches:
- CameraCapture: `start()/stop()` vs `open()/close()`, tuple return vs FrameResult
- FeatureTracker: expects FrameFeatures vs raw landmarks
- Prompts: `build_text_prompt` vs `format_text_prompt`, missing `build_vision_prompt`
- MetricsCollector: different constructor, missing record methods
**Status**: Reported to foundation-dev and exp1-dev. Awaiting fix.

### HIGH: Vision llama.cpp chat_handler
`run_vision_llama_cpp.py` sets `chat_handler=None` which will cause vision inference to fail.
**Status**: Reported to exp1-dev.

### MEDIUM: Model Path Mismatches
- download_models.py saves to `poc/models/` (flat)
- Experiment 1 scripts expect `~/.cache/local-sidekick/models/`
- Experiment 3 expects subdirectories like `models/qwen2.5-3b-instruct-gguf/`
**Status**: Reported to foundation-dev and exp23-dev.

## Failed Approaches and Lessons Learned

- **Parallel independent development** of shared modules and experiment scripts led to interface mismatches. In future, define interfaces (e.g., type stubs or protocol classes) before parallel implementation.

## Key Milestones

| Milestone | Target | Actual | Status |
|-----------|--------|--------|--------|
| Project setup complete | - | 2026-02-10 | **Done** |
| Shared modules complete | - | 2026-02-10 | **Done** (needs interface fix) |
| Experiment 1 text mode code complete | - | 2026-02-10 | **Done** (needs interface fix) |
| Experiment 1 vision mode code complete | - | 2026-02-10 | **Done** (needs chat_handler fix) |
| Experiment 2 code complete | - | 2026-02-10 | **Done** (needs interface fix) |
| Experiment 3 code complete | - | 2026-02-10 | **Done** (needs path fix) |
| Interface mismatch resolved | - | - | **BLOCKING** |
| All code reviews complete | - | - | In Progress |
| Manual testing complete | - | - | Pending |

---

_Last updated: 2026-02-10_

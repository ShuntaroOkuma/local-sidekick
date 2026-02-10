# Local Sidekick PoC - Progress Tracker

## Task Status

| # | Task | Owner | Status | Blocked By | Notes |
|---|------|-------|--------|------------|-------|
| 1 | Project setup: pyproject.toml, directory structure | foundation-dev | **Complete** | - | Reviewed: PASS |
| 2 | shared/camera.py - Camera + FaceMesh pipeline | foundation-dev | In Progress | #1 | |
| 3 | shared/features.py - Feature extraction | foundation-dev | In Progress | #1 | |
| 4 | shared/metrics.py and shared/prompts.py | foundation-dev | Pending | #1 | |
| 5 | download_models.py - Model download helper | foundation-dev | In Progress | #1 | |
| 6 | Experiment 1: Text mode (llama.cpp + MLX) | exp1-dev | In Progress | #2, #3, #4 | |
| 7 | Experiment 1: Vision mode (llama.cpp + MLX) | exp1-dev | Pending | #2, #4 | |
| 8 | Experiment 2: LM Studio (text + vision) | exp23-dev | Pending | #2, #3, #4 | |
| 9 | Experiment 3: PC usage monitoring + analysis | exp23-dev | Pending | #1, #4 | |
| 10 | README.md and PROGRESS.md | reviewer | **Complete** | - | |
| 11 | Code review: Shared modules | reviewer | Pending | #2, #3, #4 | |
| 12 | Code review: All experiments | reviewer | Pending | #6, #7, #8, #9 | |

## Per-Experiment Status

### Shared Modules
- **camera.py**: In progress (foundation-dev)
- **features.py**: In progress (foundation-dev)
- **metrics.py**: Not started
- **prompts.py**: Not started

### Experiment 1: Embedded LLM
- **run_text_llama_cpp.py**: Not started (blocked by shared modules)
- **run_text_mlx.py**: Not started (blocked by shared modules)
- **run_vision_llama_cpp.py**: Not started
- **run_vision_mlx.py**: Not started

### Experiment 2: LM Studio
- **run_text_lmstudio.py**: Not started (blocked by shared modules)
- **run_vision_lmstudio.py**: Not started

### Experiment 3: PC Usage
- **monitor.py**: Not started (blocked by task #1)
- **run_analysis.py**: Not started

## Code Reviews

| Review | File | Status | Link |
|--------|------|--------|------|
| Foundation setup | pyproject.toml, __init__.py files, docs | **PASS** | [review-foundation-setup.md](review-foundation-setup.md) |
| Shared modules | camera.py, features.py, metrics.py, prompts.py | Pending | - |
| Experiments | All experiment files | Pending | - |

## Known Issues and Blockers

_No issues reported yet. Will be updated as development progresses._

## Failed Approaches and Lessons Learned

_None yet. Will document any dead ends or pivots during implementation._

## Key Milestones

| Milestone | Target | Actual | Status |
|-----------|--------|--------|--------|
| Project setup complete | - | 2026-02-10 | **Done** |
| Shared modules complete | - | - | In Progress |
| Experiment 1 text mode working | - | - | Pending |
| Experiment 1 vision mode working | - | - | Pending |
| Experiment 2 working | - | - | Pending |
| Experiment 3 working | - | - | Pending |
| All code reviews complete | - | - | Pending |
| Manual testing complete | - | - | Pending |

---

_Last updated: 2026-02-10_

# PoC Implementation Progress

## Status Overview

| Task | Status | Owner |
|------|--------|-------|
| Project setup (pyproject.toml, dirs) | Done | foundation-dev |
| shared/camera.py | In Progress | foundation-dev |
| shared/features.py | In Progress | foundation-dev |
| shared/metrics.py | Pending | foundation-dev |
| shared/prompts.py | Pending | foundation-dev |
| download_models.py | Pending | foundation-dev |
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

## In Progress

### Shared Modules (foundation-dev)
- Working on camera.py, features.py, metrics.py, prompts.py

## Notes

- All work happens in `poc/` subdirectory
- Python 3.11+ required
- Apple Silicon (M3-M4) target environment

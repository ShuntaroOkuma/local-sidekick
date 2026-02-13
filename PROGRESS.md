# Unified Estimation Implementation Progress

## Overview
統合ルール判定 + 統合LLM判定アーキテクチャの実装。
カメラとPCの生データをまとめて判定する新しいアーキテクチャに移行する。
詳細プラン: [docs/unified-estimation-plan.md](docs/unified-estimation-plan.md)

## Base Branch
`feat/unified-estimation` (from `main`)

## PRs

| PR | Branch | Owner | Status | Description |
|---|---|---|---|---|
| [#14](https://github.com/ShuntaroOkuma/local-sidekick/pull/14) | `feat/unified-estimation-core` | estimation-core | Merged | rule_classifier.py + prompts.py + integrator.py |
| [#15](https://github.com/ShuntaroOkuma/local-sidekick/pull/15) | `feat/unified-estimation-main` | main-refactor | Merged | main.py loop restructuring |
| [#16](https://github.com/ShuntaroOkuma/local-sidekick/pull/16) | `feat/unified-estimation-tests` | test-writer | Merged | Unit tests (41 tests, all passing) |

## Completed
- [x] Plan finalized (docs/unified-estimation-plan.md)
- [x] Base branch created (feat/unified-estimation)
- [x] PR1: estimation core modules (classify_unified, prompts, integrator)
- [x] PR2: main.py loop restructuring (snapshot collection + unified classification pipeline)
- [x] PR3: Tests (41 tests, 100% pass)
- [x] All tests pass (`pytest engine/tests/ -v` → 41 passed in 0.04s)
- [x] Final integration on feat/unified-estimation branch

## Architecture (New)

```
Camera loop → store raw snapshot (no classification)
PC loop → store raw snapshot (no classification)
Integration loop:
  1. classify_unified(camera, pc) → clear cases (3 rules)
  2. LLM with UNIFIED_SYSTEM_PROMPT → ambiguous cases
  3. classify_unified_fallback() → when LLM unavailable
```

### Rules (classify_unified)
1. No face detected → away (1.0)
2. face_not_detected_ratio > 0.7 → away (0.9)
3. Camera focused (EAR>0.27, yaw<25, pitch<25, no drowsy) + PC not idle → focused (0.9)
4. Everything else → None (deferred to LLM)

### Key Design Decision
- PC idle alone does NOT trigger idle (MTG/video watching scenarios)
- Single unified LLM prompt with cross-signal reasoning

## Approaches & Notes

### Unified Estimation (2026-02-13)
- Team feature used: estimation-core created PR#14 autonomously
- In-process agents stalled after initial work (known issue)
- Remaining PRs (#15, #16) completed via Task subagents
- gemini-code-assist reviewed PR#14

### Previous: Avatar PoC (2026-02-12)
- Team + `mode: "bypassPermissions"` was successful
- 4 agents worked autonomously with PRs + reviews

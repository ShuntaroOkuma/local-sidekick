"""Model download helper for Local Sidekick PoC.

Downloads required GGUF and MLX models from Hugging Face Hub.
Supports resume on interrupted downloads and shows progress.

Usage:
    python download_models.py              # Download all models
    python download_models.py --list       # List models without downloading
    python download_models.py --text-only  # Download text models only
    python download_models.py --vision-only # Download vision models only
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class ModelSpec:
    """Specification for a model to download."""

    name: str
    repo_id: str
    filename: str | None  # None for full repo download (MLX models)
    local_dir: str
    size_gb: float
    description: str


# Model specifications based on poc-plan.md
TEXT_MODELS: tuple[ModelSpec, ...] = (
    ModelSpec(
        name="Qwen2.5-3B-Instruct (GGUF Q4_K_M)",
        repo_id="Qwen/Qwen2.5-3B-Instruct-GGUF",
        filename="qwen2.5-3b-instruct-q4_k_m.gguf",
        local_dir="qwen2.5-3b-instruct-gguf",
        size_gb=2.0,
        description="Text LLM for llama.cpp backend",
    ),
    ModelSpec(
        name="Qwen2.5-3B-Instruct-4bit (MLX)",
        repo_id="mlx-community/Qwen2.5-3B-Instruct-4bit",
        filename=None,
        local_dir="qwen2.5-3b-instruct-mlx",
        size_gb=1.8,
        description="Text LLM for MLX backend",
    ),
)

VISION_MODELS: tuple[ModelSpec, ...] = (
    ModelSpec(
        name="Qwen2-VL-2B-Instruct (GGUF Q4_K_M)",
        repo_id="Qwen/Qwen2-VL-2B-Instruct-GGUF",
        filename="qwen2-vl-2b-instruct-q4_k_m.gguf",
        local_dir="qwen2-vl-2b-instruct-gguf",
        size_gb=1.5,
        description="Vision LLM for llama.cpp backend",
    ),
    ModelSpec(
        name="Qwen2-VL-2B-Instruct-4bit (MLX)",
        repo_id="mlx-community/Qwen2-VL-2B-Instruct-4bit",
        filename=None,
        local_dir="qwen2-vl-2b-instruct-mlx",
        size_gb=1.5,
        description="Vision LLM for MLX backend",
    ),
)

ALL_MODELS: tuple[ModelSpec, ...] = TEXT_MODELS + VISION_MODELS


def get_models_dir() -> Path:
    """Return the models directory path, creating it if needed."""
    models_dir = Path(__file__).parent / "models"
    models_dir.mkdir(exist_ok=True)
    return models_dir


def print_model_list(models: Sequence[ModelSpec]) -> None:
    """Print a formatted list of models to download."""
    total_gb = sum(m.size_gb for m in models)
    print(f"\n{'=' * 60}")
    print(f"Models to download ({len(models)} models, ~{total_gb:.1f} GB total)")
    print(f"{'=' * 60}")
    for i, model in enumerate(models, 1):
        print(f"\n  {i}. {model.name}")
        print(f"     Repo:  {model.repo_id}")
        if model.filename:
            print(f"     File:  {model.filename}")
        print(f"     Size:  ~{model.size_gb:.1f} GB")
        print(f"     Use:   {model.description}")
    print(f"\n{'=' * 60}\n")


def _check_existing(model: ModelSpec, models_dir: Path) -> bool:
    """Check if a model already exists locally."""
    target = models_dir / model.local_dir
    if model.filename:
        return (target / model.filename).exists()
    # MLX models: check if directory exists and has config.json
    return (target / "config.json").exists()


def download_gguf_model(model: ModelSpec, models_dir: Path) -> Path:
    """Download a single GGUF file from Hugging Face Hub.

    Returns the path to the downloaded file.
    """
    from huggingface_hub import hf_hub_download

    target_dir = models_dir / model.local_dir
    target_dir.mkdir(exist_ok=True)

    print(f"  Downloading {model.filename} from {model.repo_id}...")
    downloaded_path = hf_hub_download(
        repo_id=model.repo_id,
        filename=model.filename,
        local_dir=str(target_dir),
        resume_download=True,
    )
    return Path(downloaded_path)


def download_mlx_model(model: ModelSpec, models_dir: Path) -> Path:
    """Download a full MLX model repository from Hugging Face Hub.

    Returns the path to the downloaded directory.
    """
    from huggingface_hub import snapshot_download

    target_dir = models_dir / model.local_dir

    print(f"  Downloading full repo {model.repo_id}...")
    downloaded_path = snapshot_download(
        repo_id=model.repo_id,
        local_dir=str(target_dir),
        resume_download=True,
    )
    return Path(downloaded_path)


def download_model(model: ModelSpec, models_dir: Path) -> bool:
    """Download a single model, returning True on success."""
    if _check_existing(model, models_dir):
        print(f"  [SKIP] {model.name} already exists")
        return True

    try:
        if model.filename:
            path = download_gguf_model(model, models_dir)
        else:
            path = download_mlx_model(model, models_dir)
        print(f"  [DONE] Saved to {path}")
        return True
    except KeyboardInterrupt:
        print("\n  [INTERRUPTED] Download paused. Run again to resume.")
        raise
    except Exception as e:
        print(f"  [ERROR] Failed to download {model.name}: {e}")
        return False


def download_models(models: Sequence[ModelSpec]) -> tuple[int, int]:
    """Download all specified models.

    Returns (success_count, failure_count).
    """
    models_dir = get_models_dir()
    success = 0
    failure = 0

    print(f"\nDownload directory: {models_dir}\n")

    for i, model in enumerate(models, 1):
        print(f"[{i}/{len(models)}] {model.name} (~{model.size_gb:.1f} GB)")
        if download_model(model, models_dir):
            success += 1
        else:
            failure += 1
        print()

    return success, failure


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Download models for Local Sidekick PoC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--list",
        action="store_true",
        help="List models without downloading",
    )
    group.add_argument(
        "--text-only",
        action="store_true",
        help="Download text models only",
    )
    group.add_argument(
        "--vision-only",
        action="store_true",
        help="Download vision models only",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for model download helper."""
    args = parse_args(argv)

    if args.text_only:
        models = TEXT_MODELS
    elif args.vision_only:
        models = VISION_MODELS
    else:
        models = ALL_MODELS

    print_model_list(models)

    if args.list:
        return 0

    try:
        success, failure = download_models(models)
    except KeyboardInterrupt:
        print("\nDownload interrupted. Run again to resume.")
        return 1

    print(f"{'=' * 60}")
    print(f"Results: {success} succeeded, {failure} failed")
    if failure > 0:
        print("Re-run to retry failed downloads.")
    print(f"{'=' * 60}")

    return 1 if failure > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

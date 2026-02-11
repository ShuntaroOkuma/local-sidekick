"""Model download helper for Local Sidekick Engine.

Downloads required GGUF and MediaPipe models.
Based on poc/download_models.py, simplified for MVP.

Usage:
    python -m engine.models.download                  # Download 3B model + MediaPipe
    python -m engine.models.download --text-only      # Download 3B model only
    python -m engine.models.download --all            # Download all models (including 7B)
    python -m engine.models.download --check          # Check which models are available
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

MODELS_DIR = Path(__file__).parent

# --- Model definitions ---


@dataclass(frozen=True)
class GGUFModel:
    """A GGUF model to download."""

    name: str
    repo_id: str
    filename: str
    description: str
    size_gb: float
    # For sharded models, list all filenames to download.
    # The first file is used by llama-cpp-python to load the full model.
    shard_filenames: tuple[str, ...] = ()


# Default model (lightweight, single file)
TEXT_MODEL_3B = GGUFModel(
    name="qwen2.5-3b-instruct-q4km",
    repo_id="Qwen/Qwen2.5-3B-Instruct-GGUF",
    filename="qwen2.5-3b-instruct-q4_k_m.gguf",
    description="Lightweight text model (default)",
    size_gb=2.0,
)

# Optional larger model (sharded into 2 files)
TEXT_MODEL_7B = GGUFModel(
    name="qwen2.5-7b-instruct-q4km",
    repo_id="Qwen/Qwen2.5-7B-Instruct-GGUF",
    filename="qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf",
    description="Recommended for text mode - better reasoning (optional, --all)",
    size_gb=4.7,
    shard_filenames=(
        "qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf",
        "qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf",
    ),
)

# MediaPipe FaceLandmarker model
_FACE_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)
_FACE_LANDMARKER_FILENAME = "face_landmarker.task"


def download_gguf_model(model: GGUFModel) -> Path:
    """Download a single GGUF model (or all shards for sharded models)."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("Error: huggingface-hub not installed.")
        print("Install with: pip install 'local-sidekick-engine[download]'")
        sys.exit(1)

    target_path = MODELS_DIR / model.filename

    if target_path.exists():
        print(f"  [skip] {model.name}: already exists at {target_path}")
        return target_path

    filenames = model.shard_filenames if model.shard_filenames else (model.filename,)
    print(f"  [download] {model.name} (~{model.size_gb}GB, {len(filenames)} file(s)): {model.description}")

    for fname in filenames:
        hf_hub_download(
            repo_id=model.repo_id,
            filename=fname,
            local_dir=str(MODELS_DIR),
        )

    print(f"  [done] Saved to {target_path}")
    return target_path


def download_face_landmarker() -> Path:
    """Download MediaPipe FaceLandmarker model from Google Storage."""
    target_path = MODELS_DIR / _FACE_LANDMARKER_FILENAME

    if target_path.exists():
        print(f"  [skip] face_landmarker: already exists at {target_path}")
        return target_path

    print("  [download] face_landmarker (~3.6MB): MediaPipe FaceLandmarker (float16)")
    urllib.request.urlretrieve(_FACE_LANDMARKER_URL, str(target_path))
    print(f"  [done] Saved to {target_path}")
    return target_path


def check_models() -> None:
    """Print status of all models."""
    print("\n=== Model Status ===\n")

    all_models: list[tuple[str, str, Path, float]] = []

    fl_path = MODELS_DIR / _FACE_LANDMARKER_FILENAME
    all_models.append(("face_landmarker", "MediaPipe FaceLandmarker float16 (camera)", fl_path, 0.004))
    all_models.append((TEXT_MODEL_3B.name, TEXT_MODEL_3B.description, MODELS_DIR / TEXT_MODEL_3B.filename, TEXT_MODEL_3B.size_gb))
    all_models.append((TEXT_MODEL_7B.name, TEXT_MODEL_7B.description, MODELS_DIR / TEXT_MODEL_7B.filename, TEXT_MODEL_7B.size_gb))

    total_size = 0.0
    downloaded_size = 0.0

    for name, desc, path, size in all_models:
        exists = path.exists()
        status = "READY" if exists else "NOT FOUND"
        marker = "+" if exists else "-"
        print(f"  [{marker}] {name} ({size}GB): {status}")
        print(f"      {desc}")
        print(f"      Path: {path}")
        total_size += size
        if exists:
            downloaded_size += size

    print(f"\n  Total: {downloaded_size:.1f}GB / {total_size:.1f}GB downloaded")
    print()


def download_models(*, text_only: bool = False, include_7b: bool = False) -> None:
    """Download models."""
    print("\n=== Downloading Models ===\n")

    errors: list[str] = []

    if not text_only:
        print("MediaPipe models:")
        try:
            download_face_landmarker()
        except Exception as e:
            print(f"  [ERROR] face_landmarker: {e}")
            errors.append("face_landmarker")
        print()

    print("Text models (GGUF):")
    try:
        download_gguf_model(TEXT_MODEL_3B)
    except Exception as e:
        print(f"  [ERROR] {TEXT_MODEL_3B.name}: {e}")
        errors.append(TEXT_MODEL_3B.name)

    if include_7b:
        try:
            download_gguf_model(TEXT_MODEL_7B)
        except Exception as e:
            print(f"  [ERROR] {TEXT_MODEL_7B.name}: {e}")
            errors.append(TEXT_MODEL_7B.name)

    if errors:
        print(f"\nCompleted with {len(errors)} error(s): {', '.join(errors)}")
    else:
        print("\nDone! Run with --check to verify.")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Download models for Local Sidekick Engine")
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Download text models only (skip MediaPipe)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all models including 7B (large, ~4.7GB extra)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check which models are already downloaded",
    )
    args = parser.parse_args()

    if args.check:
        check_models()
    else:
        download_models(text_only=args.text_only, include_7b=args.all)


if __name__ == "__main__":
    main()

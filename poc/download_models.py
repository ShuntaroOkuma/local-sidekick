"""Model download helper for Local Sidekick PoC.

Downloads required GGUF, MLX, and MediaPipe models.

Usage:
    python download_models.py              # Download all models
    python download_models.py --text-only  # Download text models only
    python download_models.py --check      # Check which models are available
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

MODELS_DIR = Path(__file__).parent / "models"

# --- Model definitions ---


@dataclass(frozen=True)
class GGUFModel:
    """A GGUF model to download."""

    name: str
    repo_id: str
    filename: str
    description: str
    size_gb: float


@dataclass(frozen=True)
class MLXModel:
    """An MLX model to download (entire repo snapshot)."""

    name: str
    repo_id: str
    description: str
    size_gb: float


TEXT_GGUF_MODELS = (
    GGUFModel(
        name="qwen2.5-3b-instruct-q4km",
        repo_id="Qwen/Qwen2.5-3B-Instruct-GGUF",
        filename="qwen2.5-3b-instruct-q4_k_m.gguf",
        description="Qwen2.5-3B-Instruct GGUF Q4_K_M (text, llama.cpp)",
        size_gb=2.0,
    ),
)

TEXT_MLX_MODELS = (
    MLXModel(
        name="qwen2.5-3b-instruct-4bit",
        repo_id="mlx-community/Qwen2.5-3B-Instruct-4bit",
        description="Qwen2.5-3B-Instruct 4-bit (text, MLX)",
        size_gb=1.8,
    ),
)

VISION_GGUF_MODELS = (
    GGUFModel(
        name="qwen2-vl-2b-instruct-q4km",
        repo_id="gaianet/Qwen2-VL-2B-Instruct-GGUF",
        filename="Qwen2-VL-2B-Instruct-Q4_K_M.gguf",
        description="Qwen2-VL-2B-Instruct GGUF Q4_K_M (vision, llama.cpp)",
        size_gb=1.5,
    ),
)

VISION_MLX_MODELS = (
    MLXModel(
        name="qwen2-vl-2b-instruct-4bit",
        repo_id="mlx-community/Qwen2-VL-2B-Instruct-4bit",
        description="Qwen2-VL-2B-Instruct 4-bit (vision, MLX)",
        size_gb=1.5,
    ),
)

# MediaPipe FaceLandmarker model (required for camera.py)
_FACE_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)
_FACE_LANDMARKER_FILENAME = "face_landmarker.task"


def _ensure_models_dir() -> None:
    """Create models directory if it doesn't exist."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


def download_gguf_model(model: GGUFModel) -> Path:
    """Download a single GGUF model file.

    Args:
        model: GGUF model definition.

    Returns:
        Path to the downloaded file.
    """
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("Error: huggingface-hub not installed.")
        print("Install with: pip install 'local-sidekick-poc[download]'")
        sys.exit(1)

    _ensure_models_dir()
    target_path = MODELS_DIR / model.filename

    if target_path.exists():
        print(f"  [skip] {model.name}: already exists at {target_path}")
        return target_path

    print(f"  [download] {model.name} (~{model.size_gb}GB): {model.description}")
    downloaded_path = hf_hub_download(
        repo_id=model.repo_id,
        filename=model.filename,
        local_dir=str(MODELS_DIR),
    )
    print(f"  [done] Saved to {downloaded_path}")
    return Path(downloaded_path)


def download_mlx_model(model: MLXModel) -> Path:
    """Download an MLX model (full repository snapshot).

    Args:
        model: MLX model definition.

    Returns:
        Path to the downloaded model directory.
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("Error: huggingface-hub not installed.")
        print("Install with: pip install 'local-sidekick-poc[download]'")
        sys.exit(1)

    _ensure_models_dir()
    target_dir = MODELS_DIR / model.name

    if target_dir.exists() and any(target_dir.iterdir()):
        print(f"  [skip] {model.name}: already exists at {target_dir}")
        return target_dir

    print(f"  [download] {model.name} (~{model.size_gb}GB): {model.description}")
    downloaded_path = snapshot_download(
        repo_id=model.repo_id,
        local_dir=str(target_dir),
    )
    print(f"  [done] Saved to {downloaded_path}")
    return Path(downloaded_path)


def download_face_landmarker() -> Path:
    """Download MediaPipe FaceLandmarker model from Google Storage.

    Returns:
        Path to the downloaded .task file.
    """
    _ensure_models_dir()
    target_path = MODELS_DIR / _FACE_LANDMARKER_FILENAME

    if target_path.exists():
        print(f"  [skip] face_landmarker: already exists at {target_path}")
        return target_path

    print(f"  [download] face_landmarker (~3.6MB): MediaPipe FaceLandmarker (float16)")
    urllib.request.urlretrieve(_FACE_LANDMARKER_URL, str(target_path))
    print(f"  [done] Saved to {target_path}")
    return target_path


def get_gguf_model_path(model_name: str) -> Optional[Path]:
    """Get the path to a downloaded GGUF model file.

    Args:
        model_name: Model name (e.g., "qwen2.5-3b-instruct-q4km").

    Returns:
        Path to the GGUF file, or None if not found.
    """
    all_gguf = TEXT_GGUF_MODELS + VISION_GGUF_MODELS
    for model in all_gguf:
        if model.name == model_name:
            path = MODELS_DIR / model.filename
            return path if path.exists() else None
    return None


def get_mlx_model_path(model_name: str) -> Optional[Path]:
    """Get the path to a downloaded MLX model directory.

    Args:
        model_name: Model name (e.g., "qwen2.5-3b-instruct-4bit").

    Returns:
        Path to the model directory, or None if not found.
    """
    all_mlx = TEXT_MLX_MODELS + VISION_MLX_MODELS
    for model in all_mlx:
        if model.name == model_name:
            path = MODELS_DIR / model.name
            return path if path.exists() and any(path.iterdir()) else None
    return None


def check_models() -> None:
    """Print status of all models."""
    print("\n=== Model Status ===\n")

    all_models: list[tuple[str, str, Path, float]] = []

    # MediaPipe FaceLandmarker
    fl_path = MODELS_DIR / _FACE_LANDMARKER_FILENAME
    all_models.append(("face_landmarker", "MediaPipe FaceLandmarker float16 (camera)", fl_path, 0.004))

    for m in TEXT_GGUF_MODELS + VISION_GGUF_MODELS:
        path = MODELS_DIR / m.filename
        all_models.append((m.name, m.description, path, m.size_gb))

    for m in TEXT_MLX_MODELS + VISION_MLX_MODELS:
        path = MODELS_DIR / m.name
        all_models.append((m.name, m.description, path, m.size_gb))

    total_size = 0.0
    downloaded_size = 0.0

    for name, desc, path, size in all_models:
        exists = path.exists() and (path.is_file() or any(path.iterdir()) if path.is_dir() else True)
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


def download_all(text_only: bool = False) -> None:
    """Download all required models.

    Args:
        text_only: If True, skip vision models.
    """
    print("\n=== Downloading Models ===\n")

    errors: list[str] = []

    print("MediaPipe models:")
    try:
        download_face_landmarker()
    except Exception as e:
        print(f"  [ERROR] face_landmarker: {e}")
        errors.append("face_landmarker")

    print("\nText models (GGUF):")
    for model in TEXT_GGUF_MODELS:
        try:
            download_gguf_model(model)
        except Exception as e:
            print(f"  [ERROR] {model.name}: {e}")
            errors.append(model.name)

    print("\nText models (MLX):")
    for model in TEXT_MLX_MODELS:
        try:
            download_mlx_model(model)
        except Exception as e:
            print(f"  [ERROR] {model.name}: {e}")
            errors.append(model.name)

    if not text_only:
        print("\nVision models (GGUF):")
        for model in VISION_GGUF_MODELS:
            try:
                download_gguf_model(model)
            except Exception as e:
                print(f"  [ERROR] {model.name}: {e}")
                errors.append(model.name)

        print("\nVision models (MLX):")
        for model in VISION_MLX_MODELS:
            try:
                download_mlx_model(model)
            except Exception as e:
                print(f"  [ERROR] {model.name}: {e}")
                errors.append(model.name)

    if errors:
        print(f"\nCompleted with {len(errors)} error(s): {', '.join(errors)}")
        print("Run 'python download_models.py --check' to see status.")
    else:
        print("\nDone! Run 'python download_models.py --check' to verify.")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Download models for Local Sidekick PoC")
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Download text models only (skip vision models)",
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
        download_all(text_only=args.text_only)


if __name__ == "__main__":
    main()

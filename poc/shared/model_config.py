"""Model path configuration for state classification experiments.

Provides centralized model path resolution with tier-based defaults.
"""

from __future__ import annotations

from pathlib import Path

# Base directory for model files
MODELS_DIR = Path(__file__).parent.parent / "models"


# --- Text mode models ---

# Recommended (7B)
TEXT_LLAMA_CPP_7B = MODELS_DIR / "qwen2.5-7b-instruct-q4_k_m.gguf"
TEXT_MLX_7B = "Qwen/Qwen2.5-7B-Instruct-4bit"

# Lightweight (3B)
TEXT_LLAMA_CPP_3B = MODELS_DIR / "qwen2.5-3b-instruct-q4_k_m.gguf"
TEXT_MLX_3B = "mlx-community/Qwen2.5-3B-Instruct-4bit"


# --- Vision mode models ---

# Recommended (7B)
VISION_LLAMA_CPP_7B = MODELS_DIR / "qwen2.5-vl-7b-instruct-q4_k_m.gguf"
VISION_MLX_7B = "Qwen/Qwen2.5-VL-7B-Instruct-4bit"

# Not recommended (2B)
VISION_LLAMA_CPP_2B = MODELS_DIR / "Qwen2-VL-2B-Instruct-Q4_K_M.gguf"
VISION_MLX_2B = "mlx-community/Qwen2-VL-2B-Instruct-4bit"


# --- MediaPipe ---
FACE_LANDMARKER = MODELS_DIR / "face_landmarker.task"


def get_text_model(backend: str, tier: str = "recommended") -> str:
    """Get text model path for the given backend and tier.

    Args:
        backend: "llama_cpp" or "mlx"
        tier: "recommended" (7B) or "lightweight" (3B)

    Returns:
        Model path string.
    """
    if backend == "llama_cpp":
        path = TEXT_LLAMA_CPP_7B if tier == "recommended" else TEXT_LLAMA_CPP_3B
        return str(path)
    elif backend == "mlx":
        return TEXT_MLX_7B if tier == "recommended" else TEXT_MLX_3B
    else:
        raise ValueError(f"Unknown backend: {backend}")


def get_vision_model(backend: str, tier: str = "recommended") -> str:
    """Get vision model path for the given backend and tier.

    Args:
        backend: "llama_cpp" or "mlx"
        tier: "recommended" (7B) or "not_recommended" (2B)

    Returns:
        Model path string.
    """
    if backend == "llama_cpp":
        path = VISION_LLAMA_CPP_7B if tier == "recommended" else VISION_LLAMA_CPP_2B
        return str(path)
    elif backend == "mlx":
        return VISION_MLX_7B if tier == "recommended" else VISION_MLX_2B
    else:
        raise ValueError(f"Unknown backend: {backend}")

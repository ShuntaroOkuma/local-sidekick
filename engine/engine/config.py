"""Configuration management for Local Sidekick Engine.

Provides centralized config with JSON persistence at ~/.local-sidekick/config.json.
Integrates model path configuration from poc/shared/model_config.py.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

# Base directories
APP_DIR = Path.home() / ".local-sidekick"
CONFIG_PATH = APP_DIR / "config.json"
DB_PATH = APP_DIR / "history.db"

# Model directory (relative to the engine/ package root)
MODELS_DIR = Path(__file__).parent.parent / "models"

# --- Model paths ---

# Text mode models (GGUF for llama-cpp-python)
TEXT_LLAMA_CPP_7B = MODELS_DIR / "qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf"
TEXT_LLAMA_CPP_3B = MODELS_DIR / "qwen2.5-3b-instruct-q4_k_m.gguf"

# MediaPipe
FACE_LANDMARKER = MODELS_DIR / "face_landmarker.task"


def get_text_model(backend: str = "llama_cpp", tier: str = "lightweight") -> str:
    """Get text model path for the given backend and tier.

    Args:
        backend: "llama_cpp" (only supported backend for MVP).
        tier: "recommended" (7B) or "lightweight" (3B).

    Returns:
        Model path string.
    """
    if backend == "llama_cpp":
        path = TEXT_LLAMA_CPP_7B if tier == "recommended" else TEXT_LLAMA_CPP_3B
        return str(path)
    raise ValueError(f"Unknown backend: {backend}")


@dataclass
class EngineConfig:
    """Engine configuration with defaults."""

    # Working hours
    working_hours_start: str = "09:00"
    working_hours_end: str = "19:00"

    # Notification settings
    max_notifications_per_day: int = 6
    drowsy_cooldown_minutes: int = 15
    distracted_cooldown_minutes: int = 20
    over_focus_cooldown_minutes: int = 30
    drowsy_trigger_seconds: int = 10
    distracted_trigger_seconds: int = 120
    over_focus_window_minutes: int = 90
    over_focus_threshold_minutes: int = 80

    # Camera settings
    camera_enabled: bool = True
    camera_index: int = 0

    # Model settings
    model_tier: str = "lightweight"
    llm_n_ctx: int = 4096

    # Monitoring intervals (seconds)
    camera_frame_interval: float = 0.2
    estimation_interval: float = 5.0
    pc_poll_interval: float = 2.0
    pc_estimation_interval: float = 30.0
    integration_interval: float = 10.0

    # Avatar settings
    avatar_enabled: bool = True

    # Server settings
    engine_port: int = 18080
    sync_enabled: bool = False

    def to_dict(self) -> dict:
        """Convert to a plain dict for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> EngineConfig:
        """Create from a dict, ignoring unknown keys."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


def load_config() -> EngineConfig:
    """Load configuration from disk, or return defaults."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r") as f:
                data = json.load(f)
            return EngineConfig.from_dict(data)
        except (json.JSONDecodeError, OSError):
            pass
    return EngineConfig()


def save_config(config: EngineConfig) -> None:
    """Save configuration to disk."""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config.to_dict(), f, indent=2)

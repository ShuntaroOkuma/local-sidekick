"""Model management API routes.

Endpoints:
    GET    /api/models                    -> List all models with download status
    POST   /api/models/{model_id}/download -> Start downloading a model
    GET    /api/models/download-status    -> Get current download progress
    DELETE /api/models/{model_id}         -> Delete a downloaded model
"""

from __future__ import annotations

import logging
import ssl
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import certifi

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from engine.config import MODELS_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models")


# --- Model definitions (self-contained, no external import) ---


@dataclass(frozen=True)
class _GGUFDef:
    """Definition for a downloadable GGUF model."""

    repo_id: str
    filename: str
    shard_filenames: tuple[str, ...] = ()


_GGUF_3B = _GGUFDef(
    repo_id="Qwen/Qwen2.5-3B-Instruct-GGUF",
    filename="qwen2.5-3b-instruct-q4_k_m.gguf",
)

_GGUF_7B = _GGUFDef(
    repo_id="Qwen/Qwen2.5-7B-Instruct-GGUF",
    filename="qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf",
    shard_filenames=(
        "qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf",
        "qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf",
    ),
)

_FACE_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)
_FACE_LANDMARKER_FILENAME = "face_landmarker.task"


_MODEL_REGISTRY: dict[str, dict] = {
    "qwen2.5-3b": {
        "name": "軽量モデル (3B)",
        "description": "高速、省メモリ。基本的な判定に最適",
        "size_gb": 2.0,
        "tier": "lightweight",
        "gguf": _GGUF_3B,
    },
    "qwen2.5-7b": {
        "name": "推奨モデル (7B)",
        "description": "高精度。より正確な状態判定",
        "size_gb": 4.7,
        "tier": "recommended",
        "gguf": _GGUF_7B,
    },
    "face_landmarker": {
        "name": "顔認識モデル",
        "description": "カメラによる状態検知に必要",
        "size_gb": 0.004,
        "tier": "vision",
        "gguf": None,
    },
}


# --- Download state tracking ---

_download_state: dict[str, dict] = {}
_download_lock = threading.Lock()


# --- Response models ---


class ModelInfo(BaseModel):
    id: str
    name: str
    description: str
    size_gb: float
    tier: str
    downloaded: bool
    downloading: bool
    error: Optional[str] = None


class ModelActionResponse(BaseModel):
    status: str
    message: str


# --- Helpers ---


def _is_model_downloaded(model_id: str) -> bool:
    """Check if a model's files exist on disk."""
    if model_id == "face_landmarker":
        return (MODELS_DIR / _FACE_LANDMARKER_FILENAME).exists()

    entry = _MODEL_REGISTRY.get(model_id)
    if entry is None or entry["gguf"] is None:
        return False

    gguf: _GGUFDef = entry["gguf"]
    filenames_to_check = (
        gguf.shard_filenames if gguf.shard_filenames else (gguf.filename,)
    )
    return all((MODELS_DIR / fname).exists() for fname in filenames_to_check)


def _build_model_list() -> list[ModelInfo]:
    """Build the full model list with current status."""
    models: list[ModelInfo] = []

    with _download_lock:
        state_snapshot = dict(_download_state)

    for model_id, entry in _MODEL_REGISTRY.items():
        dl = state_snapshot.get(model_id, {})
        models.append(
            ModelInfo(
                id=model_id,
                name=entry["name"],
                description=entry["description"],
                size_gb=entry["size_gb"],
                tier=entry["tier"],
                downloaded=_is_model_downloaded(model_id),
                downloading=dl.get("status") == "downloading",
                error=dl.get("error"),
            )
        )

    return models


def _download_gguf(gguf: _GGUFDef) -> None:
    """Download a GGUF model via huggingface_hub."""
    from huggingface_hub import hf_hub_download

    filenames = gguf.shard_filenames if gguf.shard_filenames else (gguf.filename,)
    for fname in filenames:
        hf_hub_download(
            repo_id=gguf.repo_id,
            filename=fname,
            local_dir=str(MODELS_DIR),
        )


def _download_face_landmarker() -> None:
    """Download MediaPipe FaceLandmarker model."""
    target = MODELS_DIR / _FACE_LANDMARKER_FILENAME
    if not target.exists():
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        req = urllib.request.Request(_FACE_LANDMARKER_URL)
        with urllib.request.urlopen(req, context=ssl_context) as resp:
            target.write_bytes(resp.read())


def _download_worker(model_id: str) -> None:
    """Background thread that downloads a single model."""
    try:
        if model_id == "face_landmarker":
            _download_face_landmarker()
        else:
            entry = _MODEL_REGISTRY[model_id]
            _download_gguf(entry["gguf"])

        with _download_lock:
            _download_state[model_id] = {"status": "completed", "error": None}
        logger.info("Model %s downloaded successfully.", model_id)

    except Exception as e:
        logger.error("Failed to download model %s: %s", model_id, e)
        with _download_lock:
            _download_state[model_id] = {"status": "error", "error": str(e)}


# --- Route handlers ---


@router.get("", response_model=list[ModelInfo])
async def list_models() -> list[ModelInfo]:
    """List all available models with their download status."""
    return _build_model_list()


@router.post("/{model_id}/download", response_model=ModelActionResponse)
async def download_model(model_id: str) -> ModelActionResponse:
    """Start downloading a model in the background."""
    if model_id not in _MODEL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model_id}")

    if _is_model_downloaded(model_id):
        return ModelActionResponse(status="ok", message="既にダウンロード済みです")

    with _download_lock:
        current = _download_state.get(model_id, {})
        if current.get("status") == "downloading":
            raise HTTPException(status_code=409, detail="既にダウンロード中です")
        _download_state[model_id] = {"status": "downloading", "error": None}

    thread = threading.Thread(
        target=_download_worker,
        args=(model_id,),
        daemon=True,
        name=f"download-{model_id}",
    )
    thread.start()

    return ModelActionResponse(status="ok", message="ダウンロードを開始しました")


@router.get("/download-status")
async def download_status() -> dict[str, dict]:
    """Get current download status for all models."""
    with _download_lock:
        return dict(_download_state)


@router.delete("/{model_id}", response_model=ModelActionResponse)
async def delete_model(model_id: str) -> ModelActionResponse:
    """Delete a downloaded model from disk."""
    if model_id not in _MODEL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model_id}")

    if not _is_model_downloaded(model_id):
        raise HTTPException(status_code=404, detail="モデルがダウンロードされていません")

    try:
        if model_id == "face_landmarker":
            (MODELS_DIR / _FACE_LANDMARKER_FILENAME).unlink()
        else:
            entry = _MODEL_REGISTRY[model_id]
            gguf: _GGUFDef = entry["gguf"]
            filenames_to_delete = (
                gguf.shard_filenames if gguf.shard_filenames else (gguf.filename,)
            )
            for filename in filenames_to_delete:
                path = MODELS_DIR / filename
                if path.exists():
                    path.unlink()

        with _download_lock:
            _download_state.pop(model_id, None)

        logger.info("Model %s deleted.", model_id)
        return ModelActionResponse(status="ok", message="モデルを削除しました")

    except OSError as e:
        raise HTTPException(status_code=500, detail=f"削除に失敗しました: {e}")

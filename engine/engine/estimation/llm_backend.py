"""LLM backend wrapper for llama-cpp-python.

Extracted from poc/experiment1_embedded/run_text_llama_cpp.py.
Provides a reusable LLM inference interface for state classification.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from engine.config import get_text_model

logger = logging.getLogger(__name__)


class LLMBackend:
    """Wrapper around llama-cpp-python for text-based state classification.

    Usage:
        backend = LLMBackend()
        backend.load()
        result = backend.classify(system_prompt, user_prompt)
        backend.unload()
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        model_tier: str = "lightweight",
        n_ctx: int = 2048,
        n_gpu_layers: int = -1,
    ) -> None:
        self._model_path = model_path
        self._model_tier = model_tier
        self._n_ctx = n_ctx
        self._n_gpu_layers = n_gpu_layers
        self._model = None

    def _resolve_model_path(self) -> str:
        """Resolve model path from explicit path or tier-based default."""
        if self._model_path:
            return self._model_path

        tier_path = get_text_model("llama_cpp", tier=self._model_tier)
        if Path(tier_path).exists():
            return tier_path

        # Fallback to lightweight if recommended not found
        if self._model_tier == "recommended":
            logger.warning(
                "Recommended model not found at %s, falling back to lightweight.",
                tier_path,
            )
            fallback = get_text_model("llama_cpp", tier="lightweight")
            if Path(fallback).exists():
                return fallback

        return tier_path

    @property
    def is_loaded(self) -> bool:
        """Check if the model is currently loaded."""
        return self._model is not None

    def load(self) -> None:
        """Load the LLM model into memory with Metal GPU acceleration."""
        if self._model is not None:
            return

        try:
            from llama_cpp import Llama
        except ImportError:
            raise RuntimeError(
                "llama-cpp-python is not installed. "
                "Install with: pip install 'local-sidekick-engine[llama]'"
            )

        resolved_path = self._resolve_model_path()
        if not Path(resolved_path).exists():
            raise RuntimeError(
                f"Model file not found at {resolved_path}. "
                "Run 'python -m engine.models.download' to download models."
            )

        logger.info("Loading LLM model from %s...", resolved_path)
        self._model = Llama(
            model_path=resolved_path,
            n_gpu_layers=self._n_gpu_layers,
            n_ctx=self._n_ctx,
            verbose=False,
        )
        logger.info("LLM model loaded successfully.")

    def unload(self) -> None:
        """Unload the model and free memory."""
        if self._model is not None:
            del self._model
            self._model = None
            logger.info("LLM model unloaded.")

    def classify(self, system_prompt: str, user_prompt: str) -> dict:
        """Run inference and return parsed JSON result.

        Args:
            system_prompt: System prompt for the LLM.
            user_prompt: User prompt with data to classify.

        Returns:
            Parsed JSON dict with state, confidence, reasoning.
            On parse error, returns dict with raw_response and parse_error=True.
        """
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        response = self._model.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=128,
            temperature=0.1,
        )
        content = response["choices"][0]["message"]["content"]

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON: %s", content)
            return {"raw_response": content, "parse_error": True}

"""Tests for unified LLM prompt template.

Tests UNIFIED_SYSTEM_PROMPT constants and format_unified_prompt() which
builds the user-facing prompt with camera and PC JSON data.
"""

from __future__ import annotations

import json

from engine.estimation.prompts import (
    UNIFIED_SYSTEM_PROMPT,
    format_unified_prompt,
)


# ===========================================================================
# Tests for format_unified_prompt()
# ===========================================================================


class TestFormatUnifiedPrompt:
    """Tests for the prompt formatting function."""

    def test_both_available(self) -> None:
        """Both camera_json and pc_json provided -> both appear in output."""
        camera_json = json.dumps({
            "face_detected": True,
            "ear_average": 0.30,
            "head_pose": {"yaw": 5, "pitch": -3},
        })
        pc_json = json.dumps({
            "active_app": "Code",
            "idle_seconds": 2.0,
            "keyboard_rate_window": 50,
        })

        result = format_unified_prompt(camera_json, pc_json)

        assert isinstance(result, str)
        assert camera_json in result
        assert pc_json in result
        assert "Facial features:" in result
        assert "PC usage:" in result

    def test_camera_unavailable(self) -> None:
        """camera_json='(unavailable)' -> '(unavailable)' in camera section."""
        pc_json = json.dumps({
            "active_app": "Code",
            "idle_seconds": 2.0,
        })

        result = format_unified_prompt("(unavailable)", pc_json)

        assert "(unavailable)" in result
        assert pc_json in result

    def test_pc_unavailable(self) -> None:
        """pc_json='(unavailable)' -> '(unavailable)' in PC section."""
        camera_json = json.dumps({
            "face_detected": True,
            "ear_average": 0.30,
        })

        result = format_unified_prompt(camera_json, "(unavailable)")

        assert camera_json in result
        assert "(unavailable)" in result


# ===========================================================================
# Tests for module constants
# ===========================================================================


class TestUnifiedSystemPrompt:
    """Tests for the UNIFIED_SYSTEM_PROMPT constant."""

    def test_unified_system_prompt_exists(self) -> None:
        """UNIFIED_SYSTEM_PROMPT is a non-empty string."""
        assert isinstance(UNIFIED_SYSTEM_PROMPT, str)
        assert len(UNIFIED_SYSTEM_PROMPT) > 0

    def test_unified_system_prompt_contains_cross_signal(self) -> None:
        """Prompt contains 'CROSS-SIGNAL REASONING' section."""
        assert "CROSS-SIGNAL REASONING" in UNIFIED_SYSTEM_PROMPT

    def test_unified_system_prompt_contains_states(self) -> None:
        """Prompt contains all 5 states: focused, drowsy, distracted, away, idle."""
        for state in ("focused", "drowsy", "distracted", "away", "idle"):
            assert state in UNIFIED_SYSTEM_PROMPT, (
                f"State '{state}' not found in UNIFIED_SYSTEM_PROMPT"
            )

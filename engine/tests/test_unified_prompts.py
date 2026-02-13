"""Tests for unified prompt templates and formatting.

Tests UNIFIED_SYSTEM_PROMPT and format_unified_prompt() which prepare
combined camera + PC data for LLM classification.
"""

from __future__ import annotations

import json

import pytest

from engine.estimation.prompts import (
    UNIFIED_SYSTEM_PROMPT,
    format_unified_prompt,
)


# ---------------------------------------------------------------------------
# Tests for UNIFIED_SYSTEM_PROMPT
# ---------------------------------------------------------------------------

class TestUnifiedSystemPrompt:
    """Tests for the unified system prompt constant."""

    def test_prompt_is_non_empty_string(self):
        """UNIFIED_SYSTEM_PROMPT should be a non-empty string."""
        assert isinstance(UNIFIED_SYSTEM_PROMPT, str)
        assert len(UNIFIED_SYSTEM_PROMPT) > 0

    def test_prompt_mentions_required_states(self):
        """Prompt should reference all classification states."""
        for state in ("focused", "drowsy", "distracted", "away", "idle"):
            assert state in UNIFIED_SYSTEM_PROMPT.lower(), (
                f"State '{state}' not found in UNIFIED_SYSTEM_PROMPT"
            )

    def test_prompt_mentions_json_output(self):
        """Prompt should instruct JSON output format."""
        assert "JSON" in UNIFIED_SYSTEM_PROMPT or "json" in UNIFIED_SYSTEM_PROMPT

    def test_prompt_mentions_cross_signal_reasoning(self):
        """Prompt should include cross-signal reasoning guidance."""
        prompt_lower = UNIFIED_SYSTEM_PROMPT.lower()
        # Should mention meeting apps as context for cross-signal reasoning
        assert any(
            app in prompt_lower
            for app in ("zoom", "teams", "meet", "slack")
        ), "Prompt should mention meeting apps for cross-signal reasoning"

    def test_prompt_mentions_both_data_sources(self):
        """Prompt should reference both facial/camera and PC data."""
        prompt_lower = UNIFIED_SYSTEM_PROMPT.lower()
        assert "facial" in prompt_lower or "camera" in prompt_lower or "face" in prompt_lower
        assert "pc" in prompt_lower or "usage" in prompt_lower


# ---------------------------------------------------------------------------
# Tests for format_unified_prompt()
# ---------------------------------------------------------------------------

class TestFormatUnifiedPrompt:
    """Tests for format_unified_prompt()."""

    def test_both_data_available(self):
        """Both camera and PC JSON should appear in formatted prompt."""
        camera_json = json.dumps({
            "face_detected": True,
            "ear_average": 0.28,
            "head_pose": {"yaw": 5, "pitch": -3},
        })
        pc_json = json.dumps({
            "active_app": "Code",
            "idle_seconds": 2.0,
            "keyboard_rate_window": 50,
        })

        result = format_unified_prompt(camera_json, pc_json)

        assert isinstance(result, str)
        assert camera_json in result or "face_detected" in result
        assert pc_json in result or "active_app" in result

    def test_camera_unavailable(self):
        """When camera is unavailable, prompt should contain '(unavailable)'."""
        pc_json = json.dumps({
            "active_app": "Code",
            "idle_seconds": 2.0,
        })

        result = format_unified_prompt("(unavailable)", pc_json)

        assert "(unavailable)" in result
        assert "active_app" in result or pc_json in result

    def test_pc_unavailable(self):
        """When PC data is unavailable, prompt should contain '(unavailable)'."""
        camera_json = json.dumps({
            "face_detected": True,
            "ear_average": 0.30,
        })

        result = format_unified_prompt(camera_json, "(unavailable)")

        assert "(unavailable)" in result
        assert "face_detected" in result or camera_json in result

    def test_both_unavailable(self):
        """When both are unavailable, prompt should contain both markers."""
        result = format_unified_prompt("(unavailable)", "(unavailable)")

        assert result.count("(unavailable)") == 2

    def test_result_is_string(self):
        """format_unified_prompt should return a string."""
        result = format_unified_prompt("{}", "{}")

        assert isinstance(result, str)

    def test_prompt_mentions_json_response(self):
        """Formatted prompt should instruct the model to respond with JSON."""
        result = format_unified_prompt("{}", "{}")

        result_lower = result.lower()
        assert "json" in result_lower

    def test_prompt_has_camera_and_pc_sections(self):
        """Formatted prompt should have distinct sections for camera and PC data."""
        camera_json = json.dumps({"face_detected": True})
        pc_json = json.dumps({"active_app": "Code"})

        result = format_unified_prompt(camera_json, pc_json)

        # The template from the plan has "Facial features:" and "PC usage:" sections
        result_lower = result.lower()
        assert ("facial" in result_lower or "camera" in result_lower)
        assert ("pc" in result_lower or "usage" in result_lower)

    def test_large_json_data(self):
        """Should handle full-sized snapshot data without errors."""
        camera_json = json.dumps({
            "face_detected": True,
            "ear_average": 0.28,
            "perclos": 0.03,
            "perclos_drowsy": False,
            "yawning": False,
            "blinks_per_minute": 16,
            "head_pose": {"yaw": 5, "pitch": -3, "roll": 1},
            "gaze_off_screen_ratio": 0.05,
            "head_movement_count": 2,
            "face_not_detected_ratio": 0.0,
            "ear_average_window": 0.29,
            "eyes_half_closed_ratio": 0.02,
            "head_yaw_max_abs": 12,
        }, indent=2)
        pc_json = json.dumps({
            "active_app": "Code",
            "idle_seconds": 2.0,
            "is_idle": False,
            "keyboard_rate_window": 50,
            "mouse_rate_window": 120,
            "app_switches_in_window": 1,
            "unique_apps_in_window": 2,
            "seconds_since_last_keyboard": 3,
        }, indent=2)

        result = format_unified_prompt(camera_json, pc_json)

        assert isinstance(result, str)
        assert len(result) > len(camera_json) + len(pc_json)

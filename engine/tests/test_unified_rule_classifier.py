"""Tests for unified rule classifier.

Tests classify_unified() and classify_unified_fallback() which operate on
combined camera + PC snapshot data for state estimation.
"""

from __future__ import annotations

from engine.estimation.rule_classifier import (
    ClassificationResult,
    classify_unified,
    classify_unified_fallback,
)


# ---------------------------------------------------------------------------
# Helper factories: reusable camera and PC snapshot data
# ---------------------------------------------------------------------------


def make_camera_snapshot(**overrides: object) -> dict:
    """Create a camera snapshot dict with sensible defaults."""
    base = {
        "face_detected": True,
        "ear_average": 0.30,
        "perclos": 0.05,
        "perclos_drowsy": False,
        "yawning": False,
        "head_pose": {"yaw": 0, "pitch": 0, "roll": 0},
        "gaze_off_screen_ratio": 0.1,
        "blinks_per_minute": 17,
        "head_movement_count": 2,
        "face_not_detected_ratio": 0.0,
    }
    base.update(overrides)
    return base


def make_pc_snapshot(**overrides: object) -> dict:
    """Create a PC usage snapshot dict with sensible defaults."""
    base = {
        "active_app": "Code",
        "idle_seconds": 5,
        "is_idle": False,
        "keyboard_rate_window": 120,
        "mouse_rate_window": 80,
        "app_switches_in_window": 2,
        "unique_apps_in_window": 2,
        "seconds_since_last_keyboard": 3,
    }
    base.update(overrides)
    return base


# ===========================================================================
# Tests for classify_unified()
# ===========================================================================


class TestClassifyUnified:
    """Tests for the unified rule classifier (obvious cases only)."""

    # -- Rule 1: No face detected -> away --

    def test_no_face_returns_away(self) -> None:
        """camera face_detected=False -> away (1.0), regardless of PC data."""
        camera = make_camera_snapshot(face_detected=False)
        pc = make_pc_snapshot()

        result = classify_unified(camera, pc)

        assert result is not None
        assert result.state == "away"
        assert result.confidence == 1.0
        assert result.source == "rule"

    # -- Rule 2: High face_not_detected_ratio -> away --

    def test_high_face_not_detected_ratio_returns_away(self) -> None:
        """face_not_detected_ratio > 0.7 -> away (0.9)."""
        camera = make_camera_snapshot(face_not_detected_ratio=0.8)
        pc = make_pc_snapshot()

        result = classify_unified(camera, pc)

        assert result is not None
        assert result.state == "away"
        assert result.confidence == 0.9
        assert result.source == "rule"

    # -- Rule 3: Camera focused + PC not idle -> focused --

    def test_camera_focused_pc_active_returns_focused(self) -> None:
        """EAR>0.27, yaw<25, pitch<25, no drowsy, PC not idle -> focused (0.9)."""
        camera = make_camera_snapshot(
            ear_average=0.30,
            head_pose={"yaw": 5, "pitch": -3},
            perclos_drowsy=False,
            yawning=False,
        )
        pc = make_pc_snapshot(is_idle=False, idle_seconds=2)

        result = classify_unified(camera, pc)

        assert result is not None
        assert result.state == "focused"
        assert result.confidence == 0.9
        assert result.source == "rule"

    # -- Ambiguous cases that return None (LLM needed) --

    def test_pc_idle_camera_facing_returns_none(self) -> None:
        """PC idle but camera facing screen -> None (LLM needed, could be MTG)."""
        camera = make_camera_snapshot(
            ear_average=0.28,
            head_pose={"yaw": 3, "pitch": -5},
            perclos_drowsy=False,
            yawning=False,
        )
        pc = make_pc_snapshot(is_idle=True, idle_seconds=75)

        result = classify_unified(camera, pc)

        assert result is None

    def test_head_turned_35_returns_none(self) -> None:
        """yaw=35 deg -> None (not distracted, could be talking to colleague)."""
        camera = make_camera_snapshot(
            ear_average=0.29,
            head_pose={"yaw": 35, "pitch": -2},
            perclos_drowsy=False,
            yawning=False,
        )
        pc = make_pc_snapshot()

        result = classify_unified(camera, pc)

        # 35 degrees exceeds the 25-degree threshold for the focused rule,
        # but is not enough for auto-distracted. Should go to LLM.
        assert result is None

    def test_drowsy_signals_returns_none(self) -> None:
        """perclos_drowsy=True -> None (LLM decides severity)."""
        camera = make_camera_snapshot(
            ear_average=0.19,
            perclos_drowsy=True,
            yawning=True,
            head_pose={"yaw": -2, "pitch": 15},
            blinks_per_minute=8,
        )
        pc = make_pc_snapshot()

        result = classify_unified(camera, pc)

        assert result is None

    # -- Missing data edge cases --

    def test_camera_none_pc_idle_returns_none(self) -> None:
        """camera=None, PC idle -> None (PC idle alone doesn't determine state)."""
        pc = make_pc_snapshot(is_idle=True, idle_seconds=75)

        result = classify_unified(None, pc)

        assert result is None

    def test_camera_away_pc_none_returns_away(self) -> None:
        """camera face_detected=False, pc=None -> away."""
        camera = make_camera_snapshot(face_detected=False)

        result = classify_unified(camera, None)

        assert result is not None
        assert result.state == "away"
        assert result.confidence == 1.0

    def test_both_none_returns_unknown(self) -> None:
        """Both None -> unknown (0.0)."""
        result = classify_unified(None, None)

        assert result is not None
        assert result.state == "unknown"
        assert result.confidence == 0.0

    def test_camera_none_returns_none(self) -> None:
        """camera=None, pc has data -> None (no rule applies without camera)."""
        pc = make_pc_snapshot()

        result = classify_unified(None, pc)

        assert result is None


# ===========================================================================
# Tests for classify_unified_fallback()
# ===========================================================================


class TestClassifyUnifiedFallback:
    """Tests for the LLM fallback classifier (always returns a result)."""

    def test_perclos_and_yawning_returns_drowsy(self) -> None:
        """perclos_drowsy=True, yawning=True -> drowsy (0.7)."""
        camera = make_camera_snapshot(
            ear_average=0.19,
            perclos_drowsy=True,
            yawning=True,
            head_pose={"yaw": -2, "pitch": 15},
        )
        pc = make_pc_snapshot()

        result = classify_unified_fallback(camera, pc)

        assert result is not None
        assert result.state == "drowsy"
        assert result.confidence == 0.7

    def test_yawning_only_returns_drowsy(self) -> None:
        """yawning=True -> drowsy (0.6)."""
        camera = make_camera_snapshot(
            perclos_drowsy=False,
            yawning=True,
            head_pose={"yaw": 3, "pitch": -2},
        )
        pc = make_pc_snapshot()

        result = classify_unified_fallback(camera, pc)

        assert result is not None
        assert result.state == "drowsy"
        assert result.confidence == 0.6

    def test_large_yaw_returns_distracted(self) -> None:
        """yaw > 45 deg -> distracted (0.6)."""
        camera = make_camera_snapshot(
            perclos_drowsy=False,
            yawning=False,
            head_pose={"yaw": 50, "pitch": 0},
        )
        pc = make_pc_snapshot()

        result = classify_unified_fallback(camera, pc)

        assert result is not None
        assert result.state == "distracted"
        assert result.confidence == 0.6

    def test_high_app_switches_returns_distracted(self) -> None:
        """app_switches > 6, unique_apps > 4 -> distracted (0.6)."""
        camera = make_camera_snapshot(
            perclos_drowsy=False,
            yawning=False,
            head_pose={"yaw": 3, "pitch": -5},
        )
        pc = make_pc_snapshot(
            app_switches_in_window=8,
            unique_apps_in_window=6,
        )

        result = classify_unified_fallback(camera, pc)

        assert result is not None
        assert result.state == "distracted"
        assert result.confidence == 0.6

    def test_normal_state_returns_focused(self) -> None:
        """No strong signals -> focused (0.5)."""
        camera = make_camera_snapshot(
            perclos_drowsy=False,
            yawning=False,
            head_pose={"yaw": 3, "pitch": -5},
        )
        pc = make_pc_snapshot()

        result = classify_unified_fallback(camera, pc)

        assert result is not None
        assert result.state == "focused"
        assert result.confidence == 0.5

    def test_both_none_returns_focused(self) -> None:
        """Both None -> focused (0.5) as default fallback."""
        result = classify_unified_fallback(None, None)

        assert result is not None
        assert result.state == "focused"
        assert result.confidence == 0.5

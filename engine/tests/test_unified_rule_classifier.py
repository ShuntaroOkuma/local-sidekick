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
        """EAR>0.27, yaw<40, pitch<30, no drowsy, PC not idle -> focused (0.9)."""
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

    def test_pc_idle_camera_facing_returns_focused(self) -> None:
        """PC idle but camera facing screen -> focused (reading/watching)."""
        camera = make_camera_snapshot(
            ear_average=0.28,
            head_pose={"yaw": 3, "pitch": -5},
            perclos_drowsy=False,
            yawning=False,
        )
        pc = make_pc_snapshot(is_idle=True, idle_seconds=75)

        result = classify_unified(camera, pc)

        assert result is not None
        assert result.state == "focused"
        assert result.confidence == 0.75
        assert result.source == "rule"

    def test_head_turned_35_returns_focused(self) -> None:
        """yaw=35 deg with clear signals -> focused (within 40° threshold)."""
        camera = make_camera_snapshot(
            ear_average=0.29,
            head_pose={"yaw": 35, "pitch": -2},
            perclos_drowsy=False,
            yawning=False,
        )
        pc = make_pc_snapshot()

        result = classify_unified(camera, pc)

        # 35 degrees is within the 40-degree threshold for focused rule
        assert result is not None
        assert result.state == "focused"
        assert result.confidence == 0.9

    def test_head_turned_42_returns_focused_multi_monitor(self) -> None:
        """yaw=42 deg with PC active -> focused (multi-monitor rule)."""
        camera = make_camera_snapshot(
            ear_average=0.29,
            head_pose={"yaw": 42, "pitch": -2},
            perclos_drowsy=False,
            yawning=False,
        )
        pc = make_pc_snapshot()

        result = classify_unified(camera, pc)

        assert result is not None
        assert result.state == "focused"
        assert result.confidence == 0.75
        assert result.source == "rule"

    def test_head_turned_65_returns_none(self) -> None:
        """yaw=65 deg -> None (exceeds 60° multi-monitor threshold, LLM needed)."""
        camera = make_camera_snapshot(
            ear_average=0.29,
            head_pose={"yaw": 65, "pitch": -2},
            perclos_drowsy=False,
            yawning=False,
        )
        pc = make_pc_snapshot()

        result = classify_unified(camera, pc)

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

    def test_camera_present_pc_none_returns_none(self) -> None:
        """camera present (not away), pc=None -> None (LLM needed)."""
        camera = make_camera_snapshot(
            ear_average=0.30,
            head_pose={"yaw": 5, "pitch": -3},
            perclos_drowsy=False,
            yawning=False,
        )

        result = classify_unified(camera, None)

        # Camera shows focused signals but PC is unavailable;
        # cannot confirm "pc not idle" so defers to LLM.
        assert result is None

    def test_safari_passive_browsing_with_clear_focus_signals(self) -> None:
        """Safari browsing with clear camera focused signals -> focused.

        When camera shows EAR>0.27, yaw<40, pitch<30, no drowsy and PC is
        not idle, the focused rule fires even for Safari browsing. The
        browsing pattern (low keyboard + high mouse) is for LLM to evaluate
        only when camera signals are ambiguous.
        """
        camera = make_camera_snapshot(
            ear_average=0.28,
            head_pose={"yaw": 3, "pitch": -5},
            perclos_drowsy=False,
            yawning=False,
        )
        pc = make_pc_snapshot(
            active_app="Safari",
            keyboard_rate_window=1,
            mouse_rate_window=180,
            seconds_since_last_keyboard=55,
        )

        result = classify_unified(camera, pc)

        # Camera focused signals + PC not idle -> rule 3 fires
        assert result is not None
        assert result.state == "focused"
        assert result.confidence == 0.9

    def test_safari_passive_browsing_without_ear_returns_none(self) -> None:
        """Safari browsing with missing EAR -> None (LLM determines).

        Without ear_average, the focused rule cannot fire, so the
        ambiguous browsing pattern goes to LLM.
        """
        camera = {
            "face_detected": True,
            "perclos_drowsy": False,
            "yawning": False,
            "head_pose": {"yaw": 3, "pitch": -5},
            "face_not_detected_ratio": 0.0,
        }
        pc = make_pc_snapshot(
            active_app="Safari",
            keyboard_rate_window=1,
            mouse_rate_window=180,
            seconds_since_last_keyboard=55,
        )

        result = classify_unified(camera, pc)

        assert result is None

    def test_fndr_at_boundary_does_not_trigger(self) -> None:
        """face_not_detected_ratio exactly 0.7 should NOT trigger away."""
        camera = make_camera_snapshot(face_not_detected_ratio=0.7)
        pc = make_pc_snapshot()

        result = classify_unified(camera, pc)

        # 0.7 is not > 0.7, so rule 2 should not fire
        if result is not None:
            assert result.state != "away" or result.confidence != 0.9

    def test_slightly_low_ear_pc_active_returns_focused(self) -> None:
        """EAR=0.27 (slightly low) with PC active -> focused via relaxed rule."""
        camera = make_camera_snapshot(
            ear_average=0.27,
            head_pose={"yaw": 5, "pitch": -3},
            perclos_drowsy=False,
            yawning=False,
        )
        pc = make_pc_snapshot(is_idle=False, idle_seconds=2)

        result = classify_unified(camera, pc)

        assert result is not None
        assert result.state == "focused"
        assert result.confidence == 0.8

    def test_very_low_ear_returns_none(self) -> None:
        """EAR=0.21 (below relaxed threshold) -> None (LLM needed)."""
        camera = make_camera_snapshot(
            ear_average=0.21,
            head_pose={"yaw": 5, "pitch": -3},
            perclos_drowsy=False,
            yawning=False,
        )
        pc = make_pc_snapshot(is_idle=False, idle_seconds=2)

        result = classify_unified(camera, pc)

        assert result is None

    def test_yaw_40_pc_active_returns_focused_multi_monitor(self) -> None:
        """yaw=40 with PC active -> focused via multi-monitor rule."""
        camera = make_camera_snapshot(
            ear_average=0.30,
            head_pose={"yaw": 40, "pitch": 0},
            perclos_drowsy=False,
            yawning=False,
        )
        pc = make_pc_snapshot(is_idle=False, idle_seconds=2)

        result = classify_unified(camera, pc)

        assert result is not None
        assert result.state == "focused"
        assert result.confidence == 0.75

    def test_focused_requires_pitch_below_30(self) -> None:
        """pitch >= 30 prevents all focused rules from firing."""
        camera = make_camera_snapshot(
            ear_average=0.30,
            head_pose={"yaw": 5, "pitch": 30},
            perclos_drowsy=False,
            yawning=False,
        )
        pc = make_pc_snapshot(is_idle=False, idle_seconds=2)

        result = classify_unified(camera, pc)

        # pitch 30 is not < 30, so no focused rule fires
        assert result is None

    def test_pc_idle_60s_boundary(self) -> None:
        """idle_seconds exactly 60 and is_idle=False -> PC counts as not idle."""
        camera = make_camera_snapshot(
            ear_average=0.30,
            head_pose={"yaw": 5, "pitch": -3},
            perclos_drowsy=False,
            yawning=False,
        )
        pc = make_pc_snapshot(is_idle=False, idle_seconds=60)

        result = classify_unified(camera, pc)

        # idle_seconds <= 60 and is_idle=False -> pc_not_idle is True
        assert result is not None
        assert result.state == "focused"
        assert result.confidence == 0.9

    def test_pc_idle_61s_still_focused_reading(self) -> None:
        """idle_seconds 61, camera OK -> focused (reading/watching rule)."""
        camera = make_camera_snapshot(
            ear_average=0.30,
            head_pose={"yaw": 5, "pitch": -3},
            perclos_drowsy=False,
            yawning=False,
        )
        pc = make_pc_snapshot(is_idle=False, idle_seconds=61)

        result = classify_unified(camera, pc)

        # Rule 4: PC idle but facing screen with no drowsy signs
        assert result is not None
        assert result.state == "focused"
        assert result.confidence == 0.75


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

    def test_both_none_returns_unknown(self) -> None:
        """Both None -> unknown (0.0) since no data is available."""
        result = classify_unified_fallback(None, None)

        assert result is not None
        assert result.state == "unknown"
        assert result.confidence == 0.0

    def test_camera_none_pc_high_switches_returns_distracted(self) -> None:
        """camera=None, pc with high app switches -> distracted."""
        pc = make_pc_snapshot(app_switches_in_window=8, unique_apps_in_window=6)

        result = classify_unified_fallback(None, pc)

        assert result is not None
        assert result.state == "distracted"
        assert result.confidence == 0.6

    def test_camera_none_pc_normal_returns_focused(self) -> None:
        """camera=None, pc with normal data -> focused (0.5) default."""
        pc = make_pc_snapshot()

        result = classify_unified_fallback(None, pc)

        assert result is not None
        assert result.state == "focused"
        assert result.confidence == 0.5

    def test_drowsy_takes_priority_over_distracted(self) -> None:
        """When both drowsy and distracted signals, drowsy wins (checked first)."""
        camera = make_camera_snapshot(
            ear_average=0.19,
            perclos_drowsy=True,
            yawning=True,
            head_pose={"yaw": 50, "pitch": 10},
        )
        pc = make_pc_snapshot(app_switches_in_window=8, unique_apps_in_window=6)

        result = classify_unified_fallback(camera, pc)

        assert result is not None
        assert result.state == "drowsy"

    def test_fallback_never_returns_none(self) -> None:
        """Fallback always returns ClassificationResult, never None."""
        result = classify_unified_fallback(
            make_camera_snapshot(), make_pc_snapshot()
        )

        assert result is not None
        assert isinstance(result, ClassificationResult)

    def test_fallback_source_is_rule(self) -> None:
        """Fallback results should have source='rule'."""
        result = classify_unified_fallback(
            make_camera_snapshot(), make_pc_snapshot()
        )

        assert result.source == "rule"

    def test_yaw_exactly_45_not_distracted(self) -> None:
        """yaw exactly 45 is NOT > 45, so should not trigger distracted."""
        camera = make_camera_snapshot(
            perclos_drowsy=False,
            yawning=False,
            head_pose={"yaw": 45, "pitch": 0},
        )
        pc = make_pc_snapshot()

        result = classify_unified_fallback(camera, pc)

        # yaw=45 is not > 45, so distracted rule does not fire
        assert result.state == "focused"
        assert result.confidence == 0.5

    def test_app_switches_boundary_not_distracted(self) -> None:
        """app_switches=6 and unique_apps=4 are NOT > thresholds."""
        camera = make_camera_snapshot(
            perclos_drowsy=False,
            yawning=False,
            head_pose={"yaw": 3, "pitch": -5},
        )
        pc = make_pc_snapshot(app_switches_in_window=6, unique_apps_in_window=4)

        result = classify_unified_fallback(camera, pc)

        # 6 is not > 6 and 4 is not > 4
        assert result.state == "focused"
        assert result.confidence == 0.5

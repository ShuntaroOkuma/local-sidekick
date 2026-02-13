"""Tests for unified rule classifier.

Tests classify_unified() and classify_unified_fallback() which operate on
combined camera + PC snapshot data for state estimation.
"""

from __future__ import annotations

import pytest

from engine.estimation.rule_classifier import (
    ClassificationResult,
    classify_unified,
    classify_unified_fallback,
)


# ---------------------------------------------------------------------------
# Fixtures: reusable camera and PC snapshot data
# ---------------------------------------------------------------------------

@pytest.fixture
def focused_camera_snapshot() -> dict:
    """Camera snapshot with clear focused signals."""
    return {
        "face_detected": True,
        "ear_average": 0.30,
        "perclos_drowsy": False,
        "yawning": False,
        "head_pose": {"yaw": 5, "pitch": -3},
        "gaze_off_screen_ratio": 0.05,
        "blinks_per_minute": 16,
        "head_movement_count": 1,
        "face_not_detected_ratio": 0.0,
    }


@pytest.fixture
def no_face_camera_snapshot() -> dict:
    """Camera snapshot with no face detected."""
    return {
        "face_detected": False,
        "face_not_detected_ratio": 1.0,
    }


@pytest.fixture
def high_fndr_camera_snapshot() -> dict:
    """Camera snapshot with high face_not_detected_ratio."""
    return {
        "face_detected": True,
        "face_not_detected_ratio": 0.8,
    }


@pytest.fixture
def head_turned_35_camera_snapshot() -> dict:
    """Camera with head turned 35 degrees (could be talking to colleague)."""
    return {
        "face_detected": True,
        "ear_average": 0.29,
        "perclos_drowsy": False,
        "yawning": False,
        "head_pose": {"yaw": 35, "pitch": -2},
        "gaze_off_screen_ratio": 0.2,
        "blinks_per_minute": 17,
        "head_movement_count": 2,
        "face_not_detected_ratio": 0.05,
    }


@pytest.fixture
def drowsy_camera_snapshot() -> dict:
    """Camera snapshot showing drowsiness signals."""
    return {
        "face_detected": True,
        "ear_average": 0.19,
        "perclos_drowsy": True,
        "yawning": True,
        "head_pose": {"yaw": -2, "pitch": 15},
        "gaze_off_screen_ratio": 0.1,
        "blinks_per_minute": 8,
        "head_movement_count": 0,
        "face_not_detected_ratio": 0.0,
    }


@pytest.fixture
def facing_screen_camera_snapshot() -> dict:
    """Camera snapshot: facing screen, eyes open (ambiguous without PC context)."""
    return {
        "face_detected": True,
        "ear_average": 0.28,
        "perclos_drowsy": False,
        "yawning": False,
        "head_pose": {"yaw": 3, "pitch": -5},
        "gaze_off_screen_ratio": 0.05,
        "blinks_per_minute": 15,
        "head_movement_count": 1,
        "face_not_detected_ratio": 0.0,
    }


@pytest.fixture
def active_pc_snapshot() -> dict:
    """PC snapshot showing active work (not idle)."""
    return {
        "active_app": "Code",
        "idle_seconds": 2.0,
        "is_idle": False,
        "keyboard_rate_window": 50,
        "mouse_rate_window": 120,
        "app_switches_in_window": 1,
        "unique_apps_in_window": 2,
        "seconds_since_last_keyboard": 3,
    }


@pytest.fixture
def idle_pc_snapshot() -> dict:
    """PC snapshot showing idle state (>60s no input)."""
    return {
        "active_app": "Code",
        "idle_seconds": 75.0,
        "is_idle": True,
        "keyboard_rate_window": 0,
        "mouse_rate_window": 0,
        "app_switches_in_window": 0,
        "unique_apps_in_window": 1,
        "seconds_since_last_keyboard": 80,
    }


@pytest.fixture
def safari_passive_browsing_pc_snapshot() -> dict:
    """PC snapshot: passive browsing in Safari (high mouse, low keyboard)."""
    return {
        "active_app": "Safari",
        "idle_seconds": 3.0,
        "is_idle": False,
        "keyboard_rate_window": 1,
        "mouse_rate_window": 180,
        "app_switches_in_window": 0,
        "unique_apps_in_window": 1,
        "seconds_since_last_keyboard": 55,
    }


@pytest.fixture
def high_app_switching_pc_snapshot() -> dict:
    """PC snapshot with high app switching (distraction signal)."""
    return {
        "active_app": "Finder",
        "idle_seconds": 1.0,
        "is_idle": False,
        "keyboard_rate_window": 20,
        "mouse_rate_window": 100,
        "app_switches_in_window": 8,
        "unique_apps_in_window": 6,
        "seconds_since_last_keyboard": 5,
    }


# ===========================================================================
# Tests for classify_unified()
# ===========================================================================

class TestClassifyUnified:
    """Tests for the unified rule classifier (obvious cases only)."""

    # -- Rule 1: No face detected -> away --

    def test_no_face_returns_away_with_active_pc(
        self, no_face_camera_snapshot, active_pc_snapshot
    ):
        """No face detected -> away, regardless of PC data."""
        result = classify_unified(no_face_camera_snapshot, active_pc_snapshot)

        assert result is not None
        assert result.state == "away"
        assert result.confidence == 1.0
        assert result.source == "rule"

    def test_no_face_returns_away_with_idle_pc(
        self, no_face_camera_snapshot, idle_pc_snapshot
    ):
        """No face detected -> away, even when PC is idle."""
        result = classify_unified(no_face_camera_snapshot, idle_pc_snapshot)

        assert result is not None
        assert result.state == "away"
        assert result.confidence == 1.0

    def test_no_face_returns_away_with_no_pc(self, no_face_camera_snapshot):
        """No face detected -> away, even without PC data."""
        result = classify_unified(no_face_camera_snapshot, None)

        assert result is not None
        assert result.state == "away"
        assert result.confidence == 1.0

    # -- Rule 2: High face_not_detected_ratio -> away --

    def test_high_fndr_returns_away(
        self, high_fndr_camera_snapshot, active_pc_snapshot
    ):
        """face_not_detected_ratio > 0.7 -> away."""
        result = classify_unified(high_fndr_camera_snapshot, active_pc_snapshot)

        assert result is not None
        assert result.state == "away"
        assert result.confidence == 0.9
        assert result.source == "rule"

    def test_fndr_at_boundary_not_away(self, active_pc_snapshot):
        """face_not_detected_ratio exactly 0.7 should NOT trigger away."""
        camera = {
            "face_detected": True,
            "face_not_detected_ratio": 0.7,
            "ear_average": 0.25,
            "perclos_drowsy": False,
            "yawning": False,
            "head_pose": {"yaw": 10, "pitch": 5},
        }
        result = classify_unified(camera, active_pc_snapshot)

        # Should NOT be classified as away by this rule
        if result is not None:
            assert result.state != "away" or result.confidence != 0.9

    # -- Rule 3: Camera focused + PC not idle -> focused (unified rule) --

    def test_focused_camera_and_active_pc_returns_focused(
        self, focused_camera_snapshot, active_pc_snapshot
    ):
        """Camera focused signals + PC not idle -> focused (unified rule)."""
        result = classify_unified(focused_camera_snapshot, active_pc_snapshot)

        assert result is not None
        assert result.state == "focused"
        assert result.confidence == 0.9
        assert result.source == "rule"

    def test_focused_camera_requires_pc_not_idle(
        self, focused_camera_snapshot, idle_pc_snapshot
    ):
        """Camera focused but PC idle -> None (LLM needed, could be MTG)."""
        result = classify_unified(focused_camera_snapshot, idle_pc_snapshot)

        # Should NOT return focused; should go to LLM
        assert result is None

    # -- Ambiguous cases that should return None (goes to LLM) --

    def test_pc_idle_and_facing_screen_returns_none(
        self, facing_screen_camera_snapshot, idle_pc_snapshot
    ):
        """PC idle > 60s + camera facing screen -> None (could be MTG)."""
        result = classify_unified(facing_screen_camera_snapshot, idle_pc_snapshot)

        assert result is None

    def test_head_turned_35_returns_none(
        self, head_turned_35_camera_snapshot, active_pc_snapshot
    ):
        """Head turned 35 degrees -> None (could be talking to colleague)."""
        result = classify_unified(head_turned_35_camera_snapshot, active_pc_snapshot)

        # 35 degrees should NOT be auto-classified as distracted
        assert result is None

    def test_drowsy_signals_returns_none(
        self, drowsy_camera_snapshot, active_pc_snapshot
    ):
        """Drowsy signals -> None (LLM should decide with cross-signal reasoning)."""
        result = classify_unified(drowsy_camera_snapshot, active_pc_snapshot)

        assert result is None

    def test_safari_passive_browsing_returns_none(
        self, facing_screen_camera_snapshot, safari_passive_browsing_pc_snapshot
    ):
        """Safari + low keyboard + high mouse -> None (LLM determines distraction)."""
        result = classify_unified(
            facing_screen_camera_snapshot, safari_passive_browsing_pc_snapshot
        )

        assert result is None

    # -- Missing data edge cases --

    def test_camera_none_pc_idle_returns_none(self, idle_pc_snapshot):
        """Camera=None, PC idle -> None (PC idle alone doesn't determine state)."""
        result = classify_unified(None, idle_pc_snapshot)

        assert result is None

    def test_camera_none_pc_active_returns_none(self, active_pc_snapshot):
        """Camera=None, PC active -> None (no rule match, goes to LLM)."""
        result = classify_unified(None, active_pc_snapshot)

        assert result is None

    def test_camera_away_pc_none_returns_away(self, no_face_camera_snapshot):
        """Camera away, PC=None -> away (camera away rule still applies)."""
        result = classify_unified(no_face_camera_snapshot, None)

        assert result is not None
        assert result.state == "away"

    def test_both_none_returns_unknown(self):
        """Both inputs None -> unknown with 0.0 confidence."""
        result = classify_unified(None, None)

        assert result is not None
        assert result.state == "unknown"
        assert result.confidence == 0.0

    # -- Verify ClassificationResult structure --

    def test_result_has_correct_fields(
        self, no_face_camera_snapshot, active_pc_snapshot
    ):
        """Result should be a ClassificationResult with all expected fields."""
        result = classify_unified(no_face_camera_snapshot, active_pc_snapshot)

        assert isinstance(result, ClassificationResult)
        assert hasattr(result, "state")
        assert hasattr(result, "confidence")
        assert hasattr(result, "reasoning")
        assert hasattr(result, "source")

    def test_confidence_range(self, focused_camera_snapshot, active_pc_snapshot):
        """Confidence should be between 0.0 and 1.0."""
        result = classify_unified(focused_camera_snapshot, active_pc_snapshot)

        if result is not None:
            assert 0.0 <= result.confidence <= 1.0


# ===========================================================================
# Tests for classify_unified_fallback()
# ===========================================================================

class TestClassifyUnifiedFallback:
    """Tests for the LLM fallback classifier (always returns a result)."""

    def test_perclos_and_yawning_returns_drowsy(self, drowsy_camera_snapshot, active_pc_snapshot):
        """perclos_drowsy + yawning -> drowsy with confidence 0.7."""
        result = classify_unified_fallback(drowsy_camera_snapshot, active_pc_snapshot)

        assert result is not None
        assert result.state == "drowsy"
        assert result.confidence == 0.7

    def test_yawning_only_returns_drowsy(self, active_pc_snapshot):
        """Yawning only (no perclos_drowsy) -> drowsy with lower confidence."""
        camera = {
            "face_detected": True,
            "ear_average": 0.28,
            "perclos_drowsy": False,
            "yawning": True,
            "head_pose": {"yaw": 3, "pitch": -2},
        }
        result = classify_unified_fallback(camera, active_pc_snapshot)

        assert result is not None
        assert result.state == "drowsy"
        assert result.confidence == 0.6

    def test_high_yaw_returns_distracted(self, active_pc_snapshot):
        """yaw > 45 degrees -> distracted."""
        camera = {
            "face_detected": True,
            "ear_average": 0.30,
            "perclos_drowsy": False,
            "yawning": False,
            "head_pose": {"yaw": 50, "pitch": 0},
        }
        result = classify_unified_fallback(camera, active_pc_snapshot)

        assert result is not None
        assert result.state == "distracted"
        assert result.confidence == 0.6

    def test_high_app_switches_returns_distracted(
        self, facing_screen_camera_snapshot, high_app_switching_pc_snapshot
    ):
        """app_switches > 6 and unique_apps > 4 -> distracted."""
        result = classify_unified_fallback(
            facing_screen_camera_snapshot, high_app_switching_pc_snapshot
        )

        assert result is not None
        assert result.state == "distracted"
        assert result.confidence == 0.6

    def test_normal_state_returns_focused(
        self, facing_screen_camera_snapshot, active_pc_snapshot
    ):
        """No strong signals -> focused with low confidence (0.5)."""
        result = classify_unified_fallback(
            facing_screen_camera_snapshot, active_pc_snapshot
        )

        assert result is not None
        assert result.state == "focused"
        assert result.confidence == 0.5

    def test_fallback_never_returns_none(
        self, facing_screen_camera_snapshot, active_pc_snapshot
    ):
        """Fallback should always return a ClassificationResult, never None."""
        result = classify_unified_fallback(
            facing_screen_camera_snapshot, active_pc_snapshot
        )

        assert result is not None
        assert isinstance(result, ClassificationResult)

    def test_fallback_with_none_camera(self, active_pc_snapshot):
        """Fallback with camera=None should still return a result."""
        result = classify_unified_fallback(None, active_pc_snapshot)

        assert result is not None
        assert isinstance(result, ClassificationResult)

    def test_fallback_with_none_pc(self, facing_screen_camera_snapshot):
        """Fallback with pc=None should still return a result."""
        result = classify_unified_fallback(facing_screen_camera_snapshot, None)

        assert result is not None
        assert isinstance(result, ClassificationResult)

    def test_fallback_with_both_none(self):
        """Fallback with both None should still return a result."""
        result = classify_unified_fallback(None, None)

        assert result is not None
        assert isinstance(result, ClassificationResult)

    def test_drowsy_takes_priority_over_distracted(self):
        """When both drowsy and distracted signals present, drowsy wins."""
        camera = {
            "face_detected": True,
            "ear_average": 0.19,
            "perclos_drowsy": True,
            "yawning": True,
            "head_pose": {"yaw": 50, "pitch": 10},
        }
        pc = {
            "active_app": "Finder",
            "idle_seconds": 1.0,
            "is_idle": False,
            "keyboard_rate_window": 20,
            "mouse_rate_window": 100,
            "app_switches_in_window": 8,
            "unique_apps_in_window": 6,
        }
        result = classify_unified_fallback(camera, pc)

        assert result is not None
        # Drowsy should take priority per the fallback order in the plan
        assert result.state == "drowsy"

    def test_confidence_range(self, facing_screen_camera_snapshot, active_pc_snapshot):
        """Confidence should be between 0.0 and 1.0."""
        result = classify_unified_fallback(
            facing_screen_camera_snapshot, active_pc_snapshot
        )

        assert 0.0 <= result.confidence <= 1.0

    def test_result_source_field(self, facing_screen_camera_snapshot, active_pc_snapshot):
        """Fallback results should have a source field."""
        result = classify_unified_fallback(
            facing_screen_camera_snapshot, active_pc_snapshot
        )

        assert hasattr(result, "source")

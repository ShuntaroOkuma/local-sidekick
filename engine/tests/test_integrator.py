"""Tests for the state integrator.

Tests build_integrated_state() which wraps a ClassificationResult
into an API-compatible IntegratedState dataclass.
"""

from __future__ import annotations

from engine.estimation.integrator import IntegratedState, build_integrated_state
from engine.estimation.rule_classifier import ClassificationResult


# ===========================================================================
# Tests for build_integrated_state()
# ===========================================================================


class TestBuildIntegratedState:
    """Tests for building IntegratedState from ClassificationResult."""

    def test_builds_from_classification_result(self) -> None:
        """Creates IntegratedState with correct fields from ClassificationResult."""
        result = ClassificationResult(
            state="focused",
            confidence=0.9,
            reasoning="Eyes open, facing screen, PC active",
            source="rule",
        )
        camera_snap = {"face_detected": True, "ear_average": 0.30}
        pc_snap = {"active_app": "Code", "idle_seconds": 5}

        integrated = build_integrated_state(result, camera_snap, pc_snap)

        assert isinstance(integrated, IntegratedState)
        assert integrated.state == "focused"
        assert integrated.confidence == 0.9
        assert integrated.reasoning == "Eyes open, facing screen, PC active"
        assert integrated.source == "rule"
        assert integrated.timestamp > 0

    def test_camera_and_pc_state_are_none(self) -> None:
        """camera_state and pc_state in result are always None."""
        result = ClassificationResult(
            state="drowsy",
            confidence=0.7,
            reasoning="PERCLOS drowsy and yawning detected",
            source="rule",
        )

        integrated = build_integrated_state(result, {"face_detected": True}, None)

        assert integrated.camera_state is None
        assert integrated.pc_state is None

    def test_to_dict_works(self) -> None:
        """IntegratedState.to_dict() returns proper dict with all keys."""
        result = ClassificationResult(
            state="away",
            confidence=1.0,
            reasoning="No face detected",
            source="rule",
        )

        integrated = build_integrated_state(result, None, None)
        d = integrated.to_dict()

        assert isinstance(d, dict)
        assert d["state"] == "away"
        assert d["confidence"] == 1.0
        assert d["camera_state"] is None
        assert d["pc_state"] is None
        assert d["reasoning"] == "No face detected"
        assert d["source"] == "rule"
        assert "timestamp" in d
        assert isinstance(d["timestamp"], float)

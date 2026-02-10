"""State integrator: combines camera and PC usage states.

Implements the 12-pattern integration table from the architecture design.
Camera (4 states) x PC (3 states) = 12 combinations.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class IntegratedState:
    """Result of integrating camera and PC usage states."""

    state: str  # focused, drowsy, distracted, away, idle
    confidence: float
    camera_state: Optional[str]  # focused, drowsy, distracted, away
    pc_state: Optional[str]  # focused, distracted, idle
    reasoning: str
    timestamp: float

    def to_dict(self) -> dict:
        """Convert to a plain dict for JSON/WebSocket serialization."""
        return {
            "state": self.state,
            "confidence": self.confidence,
            "camera_state": self.camera_state,
            "pc_state": self.pc_state,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp,
        }


# Integration lookup table:
# (camera_state, pc_state) -> (final_state, confidence_factor, reasoning)
_INTEGRATION_TABLE: dict[tuple[str, str], tuple[str, float, str]] = {
    # Camera: focused
    ("focused", "focused"): (
        "focused", 1.0,
        "Both camera and PC indicate focus",
    ),
    ("focused", "distracted"): (
        "focused", 0.85,
        "Camera shows focus, app switching is part of work",
    ),
    ("focused", "idle"): (
        "idle", 0.85,
        "PC idle is reliable; user is present but not active",
    ),
    # Camera: drowsy
    ("drowsy", "focused"): (
        "drowsy", 0.9,
        "Physical drowsiness detected despite PC activity",
    ),
    ("drowsy", "distracted"): (
        "drowsy", 0.9,
        "Physical drowsiness takes priority",
    ),
    ("drowsy", "idle"): (
        "drowsy", 0.95,
        "Physical drowsiness with no PC activity",
    ),
    # Camera: distracted
    ("distracted", "focused"): (
        "focused", 0.8,
        "Active typing; momentary glance away",
    ),
    ("distracted", "distracted"): (
        "distracted", 1.0,
        "Both camera and PC indicate distraction",
    ),
    ("distracted", "idle"): (
        "distracted", 0.85,
        "Looking away with no PC activity",
    ),
    # Camera: away
    ("away", "focused"): (
        "away", 0.9,
        "No face detected despite PC activity",
    ),
    ("away", "distracted"): (
        "away", 0.95,
        "No face detected, scattered PC use",
    ),
    ("away", "idle"): (
        "away", 1.0,
        "No face detected and no PC activity",
    ),
}


class StateIntegrator:
    """Integrates camera and PC usage states into a final determination.

    Handles cases where one or both inputs are unavailable.
    """

    def __init__(self) -> None:
        self._last_state: Optional[IntegratedState] = None

    @property
    def last_state(self) -> Optional[IntegratedState]:
        """Get the most recent integrated state."""
        return self._last_state

    def integrate(
        self,
        camera_state: Optional[str] = None,
        camera_confidence: float = 0.0,
        pc_state: Optional[str] = None,
        pc_confidence: float = 0.0,
    ) -> IntegratedState:
        """Combine camera and PC states into a final determination.

        Args:
            camera_state: Camera-based state (focused/drowsy/distracted/away) or None.
            camera_confidence: Confidence of camera classification.
            pc_state: PC usage state (focused/distracted/idle) or None.
            pc_confidence: Confidence of PC classification.

        Returns:
            IntegratedState with the final determination.
        """
        now = time.time()

        # Both sources available: use lookup table
        if camera_state is not None and pc_state is not None:
            key = (camera_state, pc_state)
            if key in _INTEGRATION_TABLE:
                final_state, conf_factor, reasoning = _INTEGRATION_TABLE[key]
                avg_conf = (camera_confidence + pc_confidence) / 2.0
                confidence = round(avg_conf * conf_factor, 3)
            else:
                # Unknown combination: fall back to camera state
                final_state = camera_state
                confidence = camera_confidence * 0.8
                reasoning = f"Unknown combination ({camera_state}, {pc_state}); using camera"

        # Only camera available
        elif camera_state is not None:
            final_state = camera_state
            confidence = camera_confidence * 0.9
            reasoning = "Camera only (PC monitoring unavailable)"

        # Only PC available
        elif pc_state is not None:
            final_state = pc_state
            confidence = pc_confidence * 0.8
            reasoning = "PC only (camera unavailable)"

        # Neither available
        else:
            final_state = "unknown"
            confidence = 0.0
            reasoning = "No data from camera or PC monitor"

        result = IntegratedState(
            state=final_state,
            confidence=confidence,
            camera_state=camera_state,
            pc_state=pc_state,
            reasoning=reasoning,
            timestamp=now,
        )
        self._last_state = result
        return result

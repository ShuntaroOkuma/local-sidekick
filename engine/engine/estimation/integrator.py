"""State integrator: builds IntegratedState from ClassificationResult.

Simplified from the previous 12-pattern integration table.
The unified classifier now handles cross-signal reasoning directly,
so this module just wraps the result in an API-compatible dataclass.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from engine.estimation.rule_classifier import ClassificationResult


@dataclass(frozen=True)
class IntegratedState:
    """Result of integrating camera and PC usage states."""

    state: str  # focused, drowsy, distracted, away
    confidence: float
    camera_state: Optional[str]
    pc_state: Optional[str]
    reasoning: str
    source: str  # "rule" or "llm"
    timestamp: float

    def to_dict(self) -> dict:
        """Convert to a plain dict for JSON/WebSocket serialization."""
        return {
            "state": self.state,
            "confidence": self.confidence,
            "camera_state": self.camera_state,
            "pc_state": self.pc_state,
            "reasoning": self.reasoning,
            "source": self.source,
            "timestamp": self.timestamp,
        }


def build_integrated_state(
    result: ClassificationResult,
    camera_snapshot: Optional[dict],
    pc_snapshot: Optional[dict],
) -> IntegratedState:
    """Build an IntegratedState from a unified ClassificationResult.

    Args:
        result: The classification result from unified rules or LLM.
        camera_snapshot: Raw camera snapshot dict (kept for future use).
        pc_snapshot: Raw PC snapshot dict (kept for future use).

    Returns:
        IntegratedState with camera_state and pc_state set to None
        (unified classification does not produce individual states).
    """
    return IntegratedState(
        state=result.state,
        confidence=result.confidence,
        camera_state=None,
        pc_state=None,
        reasoning=result.reasoning,
        source=result.source,
        timestamp=time.time(),
    )

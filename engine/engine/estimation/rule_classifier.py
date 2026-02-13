"""Unified rule-based classifier for obvious state detection.

Handles clear-cut cases deterministically without LLM calls.
Returns None for ambiguous cases that need LLM judgment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ClassificationResult:
    """Result of state classification."""

    state: str
    confidence: float
    reasoning: str
    source: str  # "rule" or "llm"


def _get_head_pose_values(head_pose: dict) -> tuple[float, float]:
    """Extract absolute yaw and pitch from head_pose dict."""
    yaw = abs(head_pose.get("yaw", 0))
    pitch = abs(head_pose.get("pitch", 0))
    return yaw, pitch


def classify_unified(
    camera: Optional[dict], pc: Optional[dict],
) -> Optional[ClassificationResult]:
    """Unified rule-based classification from camera and PC data.

    Returns a ClassificationResult for obvious cases, or None
    if the case is ambiguous and needs LLM judgment.

    Args:
        camera: Dict from TrackerSnapshot.to_dict(), or None if unavailable.
        pc: Dict from UsageSnapshot.to_dict(), or None if unavailable.
    """
    # Both None: no data at all
    if camera is None and pc is None:
        return ClassificationResult(
            state="unknown",
            confidence=0.0,
            reasoning="No data from camera or PC monitor",
            source="rule",
        )

    # Camera unavailable: no rules apply, defer to LLM
    if camera is None:
        return None

    # Rule 1: No face detected -> away
    if not camera.get("face_detected", True):
        return ClassificationResult(
            state="away",
            confidence=1.0,
            reasoning="No face detected in frame",
            source="rule",
        )

    # Rule 2: High face_not_detected_ratio -> away
    fndr = camera.get("face_not_detected_ratio")
    if fndr is not None and fndr > 0.7:
        return ClassificationResult(
            state="away",
            confidence=0.9,
            reasoning=f"Face not detected in {fndr:.0%} of recent frames",
            source="rule",
        )

    # PC unavailable: camera away rules already checked, defer to LLM
    if pc is None:
        return None

    # Rule 3: Clear focused (camera signals + PC not idle)
    ear_avg = camera.get("ear_average")
    perclos_drowsy = camera.get("perclos_drowsy", False)
    yawning = camera.get("yawning", False)
    head_pose = camera.get("head_pose")
    idle_seconds = pc.get("idle_seconds", 0.0)
    is_idle = pc.get("is_idle", False)

    pc_not_idle = not is_idle and idle_seconds <= 60

    if (
        ear_avg is not None
        and ear_avg > 0.27
        and not perclos_drowsy
        and not yawning
        and head_pose is not None
        and pc_not_idle
    ):
        yaw, pitch = _get_head_pose_values(head_pose)
        if yaw < 25 and pitch < 25:
            return ClassificationResult(
                state="focused",
                confidence=0.9,
                reasoning="Eyes open, facing screen, no drowsiness signals, PC active",
                source="rule",
            )

    # Ambiguous - defer to LLM
    return None


def classify_unified_fallback(
    camera: Optional[dict], pc: Optional[dict],
) -> ClassificationResult:
    """Fallback classification when LLM is unavailable.

    Always returns a ClassificationResult (never None).

    Args:
        camera: Dict from TrackerSnapshot.to_dict(), or None if unavailable.
        pc: Dict from UsageSnapshot.to_dict(), or None if unavailable.
    """
    # Camera-based fallback rules
    if camera is not None:
        perclos_drowsy = camera.get("perclos_drowsy", False)
        yawning = camera.get("yawning", False)

        # Drowsy: perclos + yawning
        if perclos_drowsy and yawning:
            return ClassificationResult(
                state="drowsy",
                confidence=0.7,
                reasoning="PERCLOS drowsy and yawning detected",
                source="rule",
            )

        # Drowsy: yawning only
        if yawning:
            return ClassificationResult(
                state="drowsy",
                confidence=0.6,
                reasoning="Yawning detected",
                source="rule",
            )

        # Distracted: large yaw
        head_pose = camera.get("head_pose")
        if head_pose is not None:
            yaw, _ = _get_head_pose_values(head_pose)
            if yaw > 45:
                return ClassificationResult(
                    state="distracted",
                    confidence=0.6,
                    reasoning=f"Head turned significantly (yaw={yaw:.0f})",
                    source="rule",
                )

    # PC-based fallback rules
    if pc is not None:
        app_switches = pc.get("app_switches_in_window", 0)
        unique_apps = pc.get("unique_apps_in_window", 0)

        if app_switches > 6 and unique_apps > 4:
            return ClassificationResult(
                state="distracted",
                confidence=0.6,
                reasoning=f"{app_switches} app switches across {unique_apps} apps",
                source="rule",
            )

    # Default: assume focused with low confidence
    return ClassificationResult(
        state="focused",
        confidence=0.5,
        reasoning="No strong signals detected, assuming focused",
        source="rule",
    )


def classify_camera_vision(face_detected: bool) -> Optional[ClassificationResult]:
    """Rule-based pre-check for vision mode.

    Only handles the trivial case (no face). Everything else needs VLM.

    Args:
        face_detected: Whether a face was detected in the frame.
    """
    if not face_detected:
        return ClassificationResult(
            state="away",
            confidence=1.0,
            reasoning="No person visible in frame",
            source="rule",
        )
    return None

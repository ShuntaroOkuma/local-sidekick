"""Rule-based pre-classifier for obvious state detection.

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


def classify_camera_text(features: dict) -> Optional[ClassificationResult]:
    """Rule-based classification from facial feature data.

    Returns a ClassificationResult for obvious cases, or None
    if the case is ambiguous and needs LLM judgment.

    Args:
        features: Dict from TrackerSnapshot.to_dict()
    """
    # Rule 1: No face detected -> away
    if not features.get("face_detected", True):
        return ClassificationResult(
            state="away",
            confidence=1.0,
            reasoning="No face detected in frame",
            source="rule",
        )

    # Rule 2: High face_not_detected_ratio -> away (mostly absent)
    fndr = features.get("face_not_detected_ratio")
    if fndr is not None and fndr > 0.7:
        return ClassificationResult(
            state="away",
            confidence=0.9,
            reasoning=f"Face not detected in {fndr:.0%} of recent frames",
            source="rule",
        )

    # Rule 3: Strong drowsy signals
    perclos_drowsy = features.get("perclos_drowsy", False)
    yawning = features.get("yawning", False)
    ear_avg = features.get("ear_average")
    ear_window = features.get("ear_average_window")
    half_closed_ratio = features.get("eyes_half_closed_ratio")

    drowsy_signals = 0
    drowsy_reasons = []

    if perclos_drowsy:
        drowsy_signals += 2
        drowsy_reasons.append("high PERCLOS")
    if yawning:
        drowsy_signals += 2
        drowsy_reasons.append("yawning detected")
    if ear_avg is not None and ear_avg < 0.20:
        drowsy_signals += 2
        drowsy_reasons.append(f"very low EAR ({ear_avg:.3f})")
    if ear_avg is not None and ear_avg < 0.25:
        drowsy_signals += 1
        drowsy_reasons.append(f"low EAR ({ear_avg:.3f})")
    if half_closed_ratio is not None and half_closed_ratio > 0.4:
        drowsy_signals += 1
        drowsy_reasons.append(f"eyes half-closed {half_closed_ratio:.0%} of time")
    if ear_window is not None and ear_window < 0.24:
        drowsy_signals += 1
        drowsy_reasons.append(f"low average EAR over window ({ear_window:.3f})")

    if drowsy_signals >= 3:
        return ClassificationResult(
            state="drowsy",
            confidence=min(0.7 + drowsy_signals * 0.05, 0.95),
            reasoning=", ".join(drowsy_reasons),
            source="rule",
        )

    # Rule 4: Strong distracted signals
    head_pose = features.get("head_pose")
    head_yaw_max = features.get("head_yaw_max_abs")
    head_movement = features.get("head_movement_count", 0)
    gaze_off = features.get("gaze_off_screen_ratio")

    distracted_signals = 0
    distracted_reasons = []

    if head_pose is not None:
        yaw = abs(head_pose.get("yaw", 0)) if isinstance(head_pose, dict) else abs(head_pose.yaw)
        pitch = abs(head_pose.get("pitch", 0)) if isinstance(head_pose, dict) else abs(head_pose.pitch)
        if yaw > 30:
            distracted_signals += 2
            distracted_reasons.append(f"head turned significantly (yaw={yaw:.0f})")
        elif yaw > 20:
            distracted_signals += 1
            distracted_reasons.append(f"head turned (yaw={yaw:.0f})")

    if head_yaw_max is not None and head_yaw_max > 25:
        distracted_signals += 1
        distracted_reasons.append(f"large yaw range (max={head_yaw_max:.0f})")
    if head_movement > 5:
        distracted_signals += 1
        distracted_reasons.append(f"frequent head movements ({head_movement})")
    if gaze_off is not None and gaze_off > 0.4:
        distracted_signals += 1
        distracted_reasons.append(f"looking away {gaze_off:.0%} of time")

    if distracted_signals >= 2:
        return ClassificationResult(
            state="distracted",
            confidence=min(0.7 + distracted_signals * 0.05, 0.95),
            reasoning=", ".join(distracted_reasons),
            source="rule",
        )

    # Rule 5: Clear focused (all indicators normal)
    if (
        ear_avg is not None and ear_avg > 0.27
        and not perclos_drowsy
        and not yawning
        and head_pose is not None
    ):
        yaw = abs(head_pose.get("yaw", 0)) if isinstance(head_pose, dict) else abs(head_pose.yaw)
        pitch = abs(head_pose.get("pitch", 0)) if isinstance(head_pose, dict) else abs(head_pose.pitch)
        if yaw < 25 and pitch < 25:
            return ClassificationResult(
                state="focused",
                confidence=0.9,
                reasoning="Eyes open, facing screen, no drowsiness or distraction signals",
                source="rule",
            )

    # Ambiguous - need LLM
    return None


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


def classify_pc_usage(usage: dict) -> Optional[ClassificationResult]:
    """Rule-based classification from PC usage data.

    Args:
        usage: Dict from UsageSnapshot.to_dict()
    """
    idle_seconds = usage.get("idle_seconds", 0.0)
    is_idle = usage.get("is_idle", False)
    app_switches = usage.get("app_switches_in_window", 0)
    unique_apps = usage.get("unique_apps_in_window", 0)
    kb_rate = usage.get("keyboard_rate_window", usage.get("keyboard_events_per_min", 0))
    mouse_rate = usage.get("mouse_rate_window", usage.get("mouse_events_per_min", 0))

    # Rule 1: Idle (highest priority)
    if idle_seconds > 60 or is_idle:
        return ClassificationResult(
            state="idle",
            confidence=0.95,
            reasoning=f"User idle for {idle_seconds:.1f}s (threshold: 60s)",
            source="rule",
        )

    # Rule 2: Clear distraction (relaxed thresholds — PoC showed
    # the previous >8 / >5+4 almost never triggered in practice)
    if app_switches > 4 or (app_switches > 2 and unique_apps > 3):
        return ClassificationResult(
            state="distracted",
            confidence=0.85,
            reasoning=f"{app_switches} app switches across {unique_apps} apps indicates fragmented attention",
            source="rule",
        )

    # Rule 3: Clear focus
    active_app = usage.get("active_app", "")
    work_apps = {"Code", "Visual Studio Code", "Terminal", "iTerm2", "Warp",
                 "Alacritty", "kitty", "IntelliJ IDEA", "PyCharm", "WebStorm",
                 "Xcode", "Vim", "Neovim", "Emacs", "Sublime Text", "Cursor", "Zed"}
    if (
        idle_seconds < 5
        and app_switches <= 2
        and kb_rate > 20
        and active_app in work_apps
    ):
        return ClassificationResult(
            state="focused",
            confidence=0.9,
            reasoning=f"Active typing in {active_app} with minimal switching",
            source="rule",
        )

    # Ambiguous - need LLM
    return None

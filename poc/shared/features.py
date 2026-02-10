"""Feature extraction from FaceMesh landmarks.

Extracts drowsiness/focus/distraction indicators:
- EAR (Eye Aspect Ratio): eye openness
- PERCLOS: percentage of eye closure over time window
- Blink detection: blink count per time window
- MAR (Mouth Aspect Ratio): yawn detection
- Head pose estimation: pitch/yaw/roll via solvePnP
"""

from __future__ import annotations

import json
import math
import time
from collections import deque
from dataclasses import asdict, dataclass
from typing import Optional

import cv2
import numpy as np

from shared.camera import Landmark

# --- Landmark indices ---
# Right eye: [33, 160, 158, 133, 153, 144]
RIGHT_EYE_INDICES = (33, 160, 158, 133, 153, 144)
# Left eye: [362, 385, 387, 263, 380, 373]
LEFT_EYE_INDICES = (362, 385, 387, 263, 380, 373)

# Mouth landmarks for MAR
UPPER_LIP_TOP = 13
LOWER_LIP_BOTTOM = 14
MOUTH_LEFT = 78
MOUTH_RIGHT = 308
UPPER_LIP_INNER_TOP = 82
LOWER_LIP_INNER_BOTTOM = 87

# Head pose estimation: 6 key points
# nose tip, chin, left eye corner, right eye corner, left mouth, right mouth
HEAD_POSE_LANDMARK_INDICES = (1, 199, 33, 263, 61, 291)

# Thresholds
EAR_CLOSED_THRESHOLD = 0.20
EAR_HALF_CLOSED_THRESHOLD = 0.25
PERCLOS_DROWSY_THRESHOLD = 0.15
MAR_YAWN_THRESHOLD = 0.6
BLINK_NORMAL_RANGE = (15, 20)  # per 60 seconds

# Time windows
PERCLOS_WINDOW_SECONDS = 60.0
BLINK_WINDOW_SECONDS = 60.0

# 3D model points for head pose (generic face model)
_MODEL_POINTS = np.array(
    [
        (0.0, 0.0, 0.0),  # nose tip
        (0.0, -330.0, -65.0),  # chin
        (-225.0, 170.0, -135.0),  # left eye left corner
        (225.0, 170.0, -135.0),  # right eye right corner
        (-150.0, -150.0, -125.0),  # left mouth corner
        (150.0, -150.0, -125.0),  # right mouth corner
    ],
    dtype=np.float64,
)


@dataclass(frozen=True)
class HeadPose:
    """Head orientation angles in degrees."""

    pitch: float  # up/down
    yaw: float  # left/right
    roll: float  # tilt


@dataclass(frozen=True)
class FrameFeatures:
    """Extracted features from a single frame."""

    timestamp: float
    face_detected: bool
    ear_right: Optional[float] = None
    ear_left: Optional[float] = None
    ear_average: Optional[float] = None
    eyes_closed: Optional[bool] = None
    eyes_half_closed: Optional[bool] = None
    mar: Optional[float] = None
    yawning: Optional[bool] = None
    head_pose: Optional[HeadPose] = None

    def to_dict(self) -> dict:
        """Convert to a plain dict for JSON serialization."""
        result = {
            "timestamp": self.timestamp,
            "face_detected": self.face_detected,
        }
        if self.face_detected:
            result.update(
                {
                    "ear_right": _round(self.ear_right),
                    "ear_left": _round(self.ear_left),
                    "ear_average": _round(self.ear_average),
                    "eyes_closed": self.eyes_closed,
                    "mar": _round(self.mar),
                    "yawning": self.yawning,
                }
            )
            if self.head_pose is not None:
                result["head_pose"] = {
                    "pitch": _round(self.head_pose.pitch),
                    "yaw": _round(self.head_pose.yaw),
                    "roll": _round(self.head_pose.roll),
                }
        return result


@dataclass(frozen=True)
class TrackerSnapshot:
    """Aggregated features over a time window."""

    timestamp: float
    face_detected: bool
    ear_average: Optional[float] = None
    eyes_closed: Optional[bool] = None
    perclos: Optional[float] = None
    perclos_drowsy: Optional[bool] = None
    blink_count: Optional[int] = None
    blinks_per_minute: Optional[float] = None
    mar: Optional[float] = None
    yawning: Optional[bool] = None
    head_pose: Optional[HeadPose] = None
    # Window statistics for EAR
    ear_average_window: Optional[float] = None
    ear_std_window: Optional[float] = None
    ear_min_window: Optional[float] = None
    eyes_half_closed_ratio: Optional[float] = None
    # Head movement statistics
    head_yaw_std: Optional[float] = None
    head_pitch_std: Optional[float] = None
    head_yaw_max_abs: Optional[float] = None
    head_pitch_max_abs: Optional[float] = None
    head_movement_count: int = 0
    gaze_off_screen_ratio: Optional[float] = None
    face_not_detected_ratio: Optional[float] = None
    frames_in_window: int = 0

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        result = {
            "timestamp": self.timestamp,
            "face_detected": self.face_detected,
        }
        if self.face_detected:
            result.update(
                {
                    "ear_average": _round(self.ear_average),
                    "eyes_closed": self.eyes_closed,
                    "perclos": _round(self.perclos),
                    "perclos_drowsy": self.perclos_drowsy,
                    "blink_count": self.blink_count,
                    "blinks_per_minute": _round(self.blinks_per_minute),
                    "mar": _round(self.mar),
                    "yawning": self.yawning,
                    "frames_in_window": self.frames_in_window,
                }
            )
            if self.head_pose is not None:
                result["head_pose"] = {
                    "pitch": _round(self.head_pose.pitch),
                    "yaw": _round(self.head_pose.yaw),
                    "roll": _round(self.head_pose.roll),
                }
            if self.ear_average_window is not None:
                result["ear_average_window"] = _round(self.ear_average_window)
                result["ear_std_window"] = _round(self.ear_std_window)
                result["ear_min_window"] = _round(self.ear_min_window)
            if self.eyes_half_closed_ratio is not None:
                result["eyes_half_closed_ratio"] = _round(self.eyes_half_closed_ratio)
            if self.head_yaw_std is not None:
                result["head_yaw_std"] = _round(self.head_yaw_std)
                result["head_pitch_std"] = _round(self.head_pitch_std)
                result["head_yaw_max_abs"] = _round(self.head_yaw_max_abs)
                result["head_pitch_max_abs"] = _round(self.head_pitch_max_abs)
                result["head_movement_count"] = self.head_movement_count
            if self.gaze_off_screen_ratio is not None:
                result["gaze_off_screen_ratio"] = _round(self.gaze_off_screen_ratio)
            if self.face_not_detected_ratio is not None:
                result["face_not_detected_ratio"] = _round(self.face_not_detected_ratio)
        return result

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


def _round(value: Optional[float], decimals: int = 3) -> Optional[float]:
    """Round a value, returning None if input is None."""
    if value is None:
        return None
    return round(value, decimals)


def _euclidean_2d(p1: Landmark, p2: Landmark) -> float:
    """Compute 2D Euclidean distance between two landmarks."""
    return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)


def compute_ear(landmarks: tuple[Landmark, ...], indices: tuple[int, ...]) -> float:
    """Compute Eye Aspect Ratio for given eye landmark indices.

    EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)

    Where indices map to: [p1, p2, p3, p4, p5, p6]
    p1-p4 = horizontal, p2-p6 and p3-p5 = vertical
    """
    p1 = landmarks[indices[0]]
    p2 = landmarks[indices[1]]
    p3 = landmarks[indices[2]]
    p4 = landmarks[indices[3]]
    p5 = landmarks[indices[4]]
    p6 = landmarks[indices[5]]

    vertical_1 = _euclidean_2d(p2, p6)
    vertical_2 = _euclidean_2d(p3, p5)
    horizontal = _euclidean_2d(p1, p4)

    if horizontal < 1e-6:
        return 0.0

    return (vertical_1 + vertical_2) / (2.0 * horizontal)


def compute_mar(landmarks: tuple[Landmark, ...]) -> float:
    """Compute Mouth Aspect Ratio for yawn detection.

    MAR = (||upper_inner - lower_inner|| + ||upper - lower||) / (2 * ||left - right||)
    """
    upper = landmarks[UPPER_LIP_TOP]
    lower = landmarks[LOWER_LIP_BOTTOM]
    left = landmarks[MOUTH_LEFT]
    right = landmarks[MOUTH_RIGHT]
    upper_inner = landmarks[UPPER_LIP_INNER_TOP]
    lower_inner = landmarks[LOWER_LIP_INNER_BOTTOM]

    vertical_1 = _euclidean_2d(upper, lower)
    vertical_2 = _euclidean_2d(upper_inner, lower_inner)
    horizontal = _euclidean_2d(left, right)

    if horizontal < 1e-6:
        return 0.0

    return (vertical_1 + vertical_2) / (2.0 * horizontal)


def estimate_head_pose(
    landmarks: tuple[Landmark, ...],
    frame_width: int,
    frame_height: int,
) -> Optional[HeadPose]:
    """Estimate head pose (pitch, yaw, roll) using cv2.solvePnP.

    Args:
        landmarks: 478 facial landmarks from FaceMesh.
        frame_width: Frame width in pixels.
        frame_height: Frame height in pixels.

    Returns:
        HeadPose with pitch/yaw/roll in degrees, or None on failure.
    """
    image_points = np.array(
        [
            (
                landmarks[idx].x * frame_width,
                landmarks[idx].y * frame_height,
            )
            for idx in HEAD_POSE_LANDMARK_INDICES
        ],
        dtype=np.float64,
    )

    focal_length = frame_width
    center = (frame_width / 2, frame_height / 2)
    camera_matrix = np.array(
        [
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1],
        ],
        dtype=np.float64,
    )
    dist_coeffs = np.zeros((4, 1), dtype=np.float64)

    success, rotation_vector, _ = cv2.solvePnP(
        _MODEL_POINTS,
        image_points,
        camera_matrix,
        dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )

    if not success:
        return None

    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)

    # Decompose rotation matrix to Euler angles
    sy = math.sqrt(rotation_matrix[0, 0] ** 2 + rotation_matrix[1, 0] ** 2)
    singular = sy < 1e-6

    if not singular:
        pitch = math.atan2(rotation_matrix[2, 1], rotation_matrix[2, 2])
        yaw = math.atan2(-rotation_matrix[2, 0], sy)
        roll = math.atan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
    else:
        pitch = math.atan2(-rotation_matrix[1, 2], rotation_matrix[1, 1])
        yaw = math.atan2(-rotation_matrix[2, 0], sy)
        roll = 0.0

    return HeadPose(
        pitch=math.degrees(pitch),
        yaw=math.degrees(yaw),
        roll=math.degrees(roll),
    )


def extract_frame_features(
    landmarks: Optional[tuple[Landmark, ...]],
    timestamp: float,
    frame_width: int = 640,
    frame_height: int = 480,
) -> FrameFeatures:
    """Extract all features from a single frame's landmarks.

    Args:
        landmarks: Facial landmarks, or None if no face detected.
        timestamp: Frame capture timestamp.
        frame_width: Frame width for head pose calculation.
        frame_height: Frame height for head pose calculation.

    Returns:
        FrameFeatures with all extracted metrics.
    """
    if landmarks is None:
        return FrameFeatures(timestamp=timestamp, face_detected=False)

    ear_right = compute_ear(landmarks, RIGHT_EYE_INDICES)
    ear_left = compute_ear(landmarks, LEFT_EYE_INDICES)
    ear_avg = (ear_right + ear_left) / 2.0
    eyes_closed = ear_avg < EAR_CLOSED_THRESHOLD
    eyes_half_closed = EAR_CLOSED_THRESHOLD <= ear_avg < EAR_HALF_CLOSED_THRESHOLD

    mar = compute_mar(landmarks)
    yawning = mar > MAR_YAWN_THRESHOLD

    head_pose = estimate_head_pose(landmarks, frame_width, frame_height)

    return FrameFeatures(
        timestamp=timestamp,
        face_detected=True,
        ear_right=ear_right,
        ear_left=ear_left,
        ear_average=ear_avg,
        eyes_closed=eyes_closed,
        eyes_half_closed=eyes_half_closed,
        mar=mar,
        yawning=yawning,
        head_pose=head_pose,
    )


@dataclass
class _BlinkState:
    """Tracks blink detection state (mutable, internal only)."""

    was_closed: bool = False
    count: int = 0


class FeatureTracker:
    """Time-series feature tracker with sliding window aggregation.

    Tracks per-frame features over a configurable time window and
    computes aggregated metrics (PERCLOS, blink rate, etc.).
    """

    def __init__(self, window_seconds: float = PERCLOS_WINDOW_SECONDS) -> None:
        self._window_seconds = window_seconds
        self._history: deque[FrameFeatures] = deque()
        self._blink_events: deque[float] = deque()  # timestamps of blink events
        self._blink_state = _BlinkState()

    def update(self, features: FrameFeatures) -> TrackerSnapshot:
        """Add a frame's features and return aggregated snapshot.

        Args:
            features: Features extracted from the current frame.

        Returns:
            TrackerSnapshot with aggregated metrics over the time window.
        """
        self._history.append(features)
        self._prune_old_entries(features.timestamp)
        self._detect_blink(features)

        if not features.face_detected:
            return TrackerSnapshot(
                timestamp=features.timestamp,
                face_detected=False,
                frames_in_window=len(self._history),
            )

        # Compute PERCLOS: fraction of frames with eyes closed
        face_frames = [f for f in self._history if f.face_detected]
        total_face_frames = len(face_frames)

        if total_face_frames > 0:
            closed_frames = sum(1 for f in face_frames if f.eyes_closed)
            perclos = closed_frames / total_face_frames
        else:
            perclos = 0.0

        # Blinks per minute
        blink_count = len(self._blink_events)
        window_duration = self._get_window_duration(features.timestamp)
        if window_duration > 0:
            blinks_per_minute = (blink_count / window_duration) * 60.0
        else:
            blinks_per_minute = 0.0

        # EAR window statistics
        ear_values = [f.ear_average for f in face_frames if f.ear_average is not None]
        if ear_values:
            ear_average_window = sum(ear_values) / len(ear_values)
            ear_min_window = min(ear_values)
            if len(ear_values) > 1:
                mean = ear_average_window
                ear_std_window = (sum((v - mean) ** 2 for v in ear_values) / len(ear_values)) ** 0.5
            else:
                ear_std_window = 0.0
        else:
            ear_average_window = None
            ear_std_window = None
            ear_min_window = None

        # Eyes half-closed ratio
        if total_face_frames > 0:
            half_closed_count = sum(
                1 for f in face_frames
                if f.eyes_half_closed is True
            )
            eyes_half_closed_ratio = half_closed_count / total_face_frames
        else:
            eyes_half_closed_ratio = None

        # Head pose statistics
        yaw_values = [
            f.head_pose.yaw for f in face_frames
            if f.head_pose is not None
        ]
        pitch_values = [
            f.head_pose.pitch for f in face_frames
            if f.head_pose is not None
        ]

        if yaw_values:
            yaw_mean = sum(yaw_values) / len(yaw_values)
            pitch_mean = sum(pitch_values) / len(pitch_values)
            head_yaw_std = (sum((v - yaw_mean) ** 2 for v in yaw_values) / len(yaw_values)) ** 0.5 if len(yaw_values) > 1 else 0.0
            head_pitch_std = (sum((v - pitch_mean) ** 2 for v in pitch_values) / len(pitch_values)) ** 0.5 if len(pitch_values) > 1 else 0.0
            head_yaw_max_abs = max(abs(v) for v in yaw_values)
            head_pitch_max_abs = max(abs(v) for v in pitch_values)
        else:
            head_yaw_std = None
            head_pitch_std = None
            head_yaw_max_abs = None
            head_pitch_max_abs = None

        # Head movement count (>5 degree change between consecutive frames)
        head_movement_count = 0
        pose_frames = [f for f in face_frames if f.head_pose is not None]
        for i in range(1, len(pose_frames)):
            prev = pose_frames[i - 1].head_pose
            curr = pose_frames[i].head_pose
            if abs(curr.yaw - prev.yaw) > 5.0 or abs(curr.pitch - prev.pitch) > 5.0:
                head_movement_count += 1

        # Gaze off-screen ratio
        if yaw_values:
            off_screen_count = sum(
                1 for f in face_frames
                if f.head_pose is not None and (abs(f.head_pose.yaw) > 15 or abs(f.head_pose.pitch) > 15)
            )
            gaze_off_screen_ratio = off_screen_count / len(face_frames)
        else:
            gaze_off_screen_ratio = None

        # Face not detected ratio (over all frames, not just face frames)
        all_frames = len(self._history)
        if all_frames > 0:
            not_detected = sum(1 for f in self._history if not f.face_detected)
            face_not_detected_ratio = not_detected / all_frames
        else:
            face_not_detected_ratio = None

        return TrackerSnapshot(
            timestamp=features.timestamp,
            face_detected=True,
            ear_average=features.ear_average,
            eyes_closed=features.eyes_closed,
            perclos=perclos,
            perclos_drowsy=perclos > PERCLOS_DROWSY_THRESHOLD,
            blink_count=blink_count,
            blinks_per_minute=blinks_per_minute,
            mar=features.mar,
            yawning=features.yawning,
            head_pose=features.head_pose,
            frames_in_window=len(self._history),
            ear_average_window=ear_average_window,
            ear_std_window=ear_std_window,
            ear_min_window=ear_min_window,
            eyes_half_closed_ratio=eyes_half_closed_ratio,
            head_yaw_std=head_yaw_std,
            head_pitch_std=head_pitch_std,
            head_yaw_max_abs=head_yaw_max_abs,
            head_pitch_max_abs=head_pitch_max_abs,
            head_movement_count=head_movement_count,
            gaze_off_screen_ratio=gaze_off_screen_ratio,
            face_not_detected_ratio=face_not_detected_ratio,
        )

    def _prune_old_entries(self, current_time: float) -> None:
        """Remove entries older than the time window."""
        cutoff = current_time - self._window_seconds
        while self._history and self._history[0].timestamp < cutoff:
            self._history.popleft()
        while self._blink_events and self._blink_events[0] < cutoff:
            self._blink_events.popleft()

    def _detect_blink(self, features: FrameFeatures) -> None:
        """Detect blink events (EAR drops below threshold then recovers)."""
        if not features.face_detected or features.eyes_closed is None:
            return

        if features.eyes_closed:
            self._blink_state = _BlinkState(
                was_closed=True,
                count=self._blink_state.count,
            )
        elif self._blink_state.was_closed:
            # Eyes just opened - count as blink
            self._blink_events.append(features.timestamp)
            self._blink_state = _BlinkState(
                was_closed=False,
                count=self._blink_state.count + 1,
            )

    def _get_window_duration(self, current_time: float) -> float:
        """Get the actual duration of data in the window."""
        if not self._history:
            return 0.0
        oldest = self._history[0].timestamp
        return current_time - oldest

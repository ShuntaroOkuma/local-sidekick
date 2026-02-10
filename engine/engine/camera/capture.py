"""Webcam capture + MediaPipe FaceLandmarker pipeline.

Provides CameraCapture class that wraps cv2.VideoCapture and MediaPipe
FaceLandmarker (Tasks API) to deliver frames with 478-point facial
landmarks (including iris landmarks).

Migrated from poc/shared/camera.py with model path updated for engine layout.
"""

from __future__ import annotations

import argparse
import base64
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    RunningMode,
)

# FaceLandmarker configuration
_NUM_FACES = 1
_MIN_DETECTION_CONFIDENCE = 0.5
_MIN_TRACKING_CONFIDENCE = 0.5

# Camera defaults
DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480
DEFAULT_CAMERA_INDEX = 0
JPEG_QUALITY = 80

# Default model path (relative to poc/ directory)
_DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "face_landmarker.task"
_MODEL_DOWNLOAD_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)


@dataclass(frozen=True)
class Landmark:
    """A single 3D facial landmark."""

    x: float
    y: float
    z: float


@dataclass(frozen=True)
class FrameResult:
    """Result of a single frame capture + face landmark detection.

    Attributes:
        frame: BGR image as numpy array (H, W, 3).
        landmarks: Tuple of 478 Landmark objects, or None if no face detected.
        timestamp: Capture time (time.monotonic()).
        face_detected: Whether a face was found in this frame.
    """

    frame: np.ndarray
    landmarks: Optional[tuple[Landmark, ...]]
    timestamp: float
    face_detected: bool


class CameraCapture:
    """Webcam + FaceLandmarker pipeline.

    Usage:
        with CameraCapture() as cam:
            result = cam.read_frame()
            if result.face_detected:
                print(f"Got {len(result.landmarks)} landmarks")
    """

    def __init__(
        self,
        camera_index: int = DEFAULT_CAMERA_INDEX,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        model_path: Optional[str] = None,
    ) -> None:
        self._camera_index = camera_index
        self._width = width
        self._height = height
        self._model_path = Path(model_path) if model_path else _DEFAULT_MODEL_PATH
        self._cap: Optional[cv2.VideoCapture] = None
        self._landmarker: Optional[FaceLandmarker] = None
        self._frame_timestamp_ms: int = 0

    def __enter__(self) -> CameraCapture:
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.close()

    def open(self) -> None:
        """Open camera and initialize FaceLandmarker."""
        if self._cap is not None:
            return

        if not self._model_path.exists():
            raise RuntimeError(
                f"FaceLandmarker model not found at {self._model_path}. "
                f"Download it with: curl -L -o {self._model_path} "
                f'"{_MODEL_DOWNLOAD_URL}"'
            )

        self._cap = cv2.VideoCapture(self._camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Failed to open camera at index {self._camera_index}. "
                "Check camera permissions in System Settings > Privacy & Security > Camera."
            )

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)

        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(self._model_path)),
            running_mode=RunningMode.VIDEO,
            num_faces=_NUM_FACES,
            min_face_detection_confidence=_MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=_MIN_TRACKING_CONFIDENCE,
        )
        self._landmarker = FaceLandmarker.create_from_options(options)
        self._frame_timestamp_ms = 0

    def close(self) -> None:
        """Release camera and FaceLandmarker resources."""
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None

        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def read_frame(self) -> FrameResult:
        """Capture a frame and run FaceLandmarker detection.

        Returns:
            FrameResult with frame data and optional landmarks.

        Raises:
            RuntimeError: If camera is not opened or frame capture fails.
        """
        if self._cap is None or self._landmarker is None:
            raise RuntimeError("Camera not opened. Call open() or use context manager.")

        ret, frame = self._cap.read()
        if not ret or frame is None:
            raise RuntimeError("Failed to capture frame from camera.")

        timestamp = time.monotonic()

        # FaceLandmarker Tasks API expects mp.Image in RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # Timestamps must be monotonically increasing in milliseconds
        self._frame_timestamp_ms += 33  # ~30fps
        result = self._landmarker.detect_for_video(mp_image, self._frame_timestamp_ms)

        landmarks = None
        face_detected = False

        if result.face_landmarks and len(result.face_landmarks) > 0:
            face_detected = True
            face_lms = result.face_landmarks[0]
            landmarks = tuple(
                Landmark(x=lm.x, y=lm.y, z=lm.z) for lm in face_lms
            )

        return FrameResult(
            frame=frame,
            landmarks=landmarks,
            timestamp=timestamp,
            face_detected=face_detected,
        )

    def get_frame_as_base64(self, quality: int = JPEG_QUALITY) -> Optional[str]:
        """Capture a frame and return it as a base64-encoded JPEG string.

        Args:
            quality: JPEG compression quality (0-100).

        Returns:
            Base64-encoded JPEG string, or None if capture fails.
        """
        try:
            result = self.read_frame()
        except RuntimeError:
            return None

        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        success, buffer = cv2.imencode(".jpg", result.frame, encode_params)
        if not success:
            return None

        return base64.b64encode(buffer.tobytes()).decode("ascii")


def _draw_landmarks_on_frame(
    frame: np.ndarray, landmarks: tuple[Landmark, ...]
) -> np.ndarray:
    """Draw landmark points on a copy of the frame for visualization."""
    display = frame.copy()
    h, w = display.shape[:2]
    for lm in landmarks:
        x = int(lm.x * w)
        y = int(lm.y * h)
        cv2.circle(display, (x, y), 1, (0, 255, 0), -1)
    return display


def main() -> None:
    """Standalone camera test with optional video display."""
    parser = argparse.ArgumentParser(description="Camera + FaceLandmarker test")
    parser.add_argument(
        "--show-video", action="store_true", help="Show video window with landmarks"
    )
    parser.add_argument(
        "--duration", type=int, default=10, help="Duration in seconds (default: 10)"
    )
    parser.add_argument(
        "--camera", type=int, default=DEFAULT_CAMERA_INDEX, help="Camera index"
    )
    args = parser.parse_args()

    print(f"Starting camera test (duration={args.duration}s, show_video={args.show_video})")

    frame_count = 0
    face_count = 0
    start_time = time.monotonic()

    with CameraCapture(camera_index=args.camera) as cam:
        while True:
            elapsed = time.monotonic() - start_time
            if elapsed >= args.duration:
                break

            result = cam.read_frame()
            frame_count += 1

            if result.face_detected:
                face_count += 1

            if args.show_video:
                display = result.frame
                if result.face_detected and result.landmarks is not None:
                    display = _draw_landmarks_on_frame(result.frame, result.landmarks)

                fps = frame_count / max(elapsed, 0.001)
                cv2.putText(
                    display,
                    f"FPS: {fps:.1f} | Face: {result.face_detected}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )
                cv2.imshow("Camera + FaceLandmarker", display)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    elapsed = time.monotonic() - start_time
    fps = frame_count / max(elapsed, 0.001)
    detection_rate = face_count / max(frame_count, 1) * 100

    print(f"\nResults:")
    print(f"  Duration:       {elapsed:.1f}s")
    print(f"  Frames:         {frame_count}")
    print(f"  FPS:            {fps:.1f}")
    print(f"  Face detected:  {face_count}/{frame_count} ({detection_rate:.1f}%)")

    if args.show_video:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

"""Tests for frame brightness check (dark frame detection).

Verifies that is_frame_too_dark() correctly identifies frames that are
too dark for meaningful face detection (lid closed, camera covered, etc.).
"""

from __future__ import annotations

import numpy as np

from engine.camera.capture import (
    DARK_FRAME_BRIGHTNESS_THRESHOLD,
    is_frame_too_dark,
)


class TestIsFrameTooDark:
    """Tests for the dark frame detection function."""

    def test_completely_black_frame_is_dark(self) -> None:
        """All-zero BGR frame should be detected as too dark."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        assert is_frame_too_dark(frame) is True

    def test_very_dim_frame_is_dark(self) -> None:
        """Frame with mean brightness below threshold is too dark."""
        frame = np.full((480, 640, 3), 5, dtype=np.uint8)
        assert is_frame_too_dark(frame) is True

    def test_normal_frame_is_not_dark(self) -> None:
        """Frame with typical indoor lighting is not dark."""
        frame = np.full((480, 640, 3), 120, dtype=np.uint8)
        assert is_frame_too_dark(frame) is False

    def test_bright_frame_is_not_dark(self) -> None:
        """Bright frame is definitely not dark."""
        frame = np.full((480, 640, 3), 200, dtype=np.uint8)
        assert is_frame_too_dark(frame) is False

    def test_threshold_boundary_below(self) -> None:
        """Frame just below threshold is dark."""
        value = DARK_FRAME_BRIGHTNESS_THRESHOLD - 1
        frame = np.full((480, 640, 3), max(value, 0), dtype=np.uint8)
        assert is_frame_too_dark(frame) is True

    def test_threshold_boundary_at(self) -> None:
        """Frame exactly at threshold is NOT dark (< not <=)."""
        frame = np.full((480, 640, 3), DARK_FRAME_BRIGHTNESS_THRESHOLD, dtype=np.uint8)
        assert is_frame_too_dark(frame) is False

    def test_custom_threshold(self) -> None:
        """Custom threshold overrides default."""
        frame = np.full((480, 640, 3), 25, dtype=np.uint8)
        assert is_frame_too_dark(frame, threshold=30) is True
        assert is_frame_too_dark(frame, threshold=20) is False

    def test_mixed_brightness_frame(self) -> None:
        """Frame with a mix of bright and dark regions uses mean."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Make top half bright (mean of whole frame ~60)
        frame[:240, :, :] = 120
        assert is_frame_too_dark(frame) is False

    def test_mostly_dark_with_tiny_bright_spot(self) -> None:
        """Mostly black frame with a small bright spot stays dark."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Small 10x10 bright spot (negligible contribution to mean)
        frame[0:10, 0:10, :] = 255
        assert is_frame_too_dark(frame) is True

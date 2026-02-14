"""Tests for compute_daily_stats() and _extract_focus_blocks_from_segments()."""

import datetime

import pytest

from engine.history.aggregator import _extract_focus_blocks_from_segments


class TestExtractFocusBlocksFromSegments:
    def test_single_focused_block(self):
        """A single focused segment >= 5min -> one block."""
        segments = [
            {
                "state": "focused",
                "start_time": 1707868800.0,  # 2024-02-14 00:00:00 UTC
                "end_time": 1707870600.0,    # 2024-02-14 00:30:00 UTC
                "duration_min": 30.0,
                "breakdown": {"focused": 1800.0},
            },
        ]
        blocks = _extract_focus_blocks_from_segments(segments)
        assert len(blocks) == 1
        assert blocks[0]["duration_min"] == 30

    def test_short_focused_block_excluded(self):
        """A focused segment < 5min -> excluded."""
        segments = [
            {
                "state": "focused",
                "start_time": 1707868800.0,
                "end_time": 1707869040.0,  # 4 minutes
                "duration_min": 4.0,
                "breakdown": {"focused": 240.0},
            },
        ]
        blocks = _extract_focus_blocks_from_segments(segments)
        assert len(blocks) == 0

    def test_non_focused_segments_ignored(self):
        """Non-focused segments are not included."""
        segments = [
            {
                "state": "drowsy",
                "start_time": 1707868800.0,
                "end_time": 1707870600.0,
                "duration_min": 30.0,
                "breakdown": {"drowsy": 1800.0},
            },
            {
                "state": "focused",
                "start_time": 1707870600.0,
                "end_time": 1707872400.0,
                "duration_min": 30.0,
                "breakdown": {"focused": 1800.0},
            },
        ]
        blocks = _extract_focus_blocks_from_segments(segments)
        assert len(blocks) == 1
        assert blocks[0]["duration_min"] == 30

    def test_multiple_focused_blocks(self):
        """Two focused segments separated by non-focused -> two blocks."""
        segments = [
            {
                "state": "focused",
                "start_time": 1707868800.0,
                "end_time": 1707870600.0,
                "duration_min": 30.0,
                "breakdown": {"focused": 1800.0},
            },
            {
                "state": "distracted",
                "start_time": 1707870600.0,
                "end_time": 1707871200.0,
                "duration_min": 10.0,
                "breakdown": {"distracted": 600.0},
            },
            {
                "state": "focused",
                "start_time": 1707871200.0,
                "end_time": 1707874800.0,
                "duration_min": 60.0,
                "breakdown": {"focused": 3600.0},
            },
        ]
        blocks = _extract_focus_blocks_from_segments(segments)
        assert len(blocks) == 2
        assert blocks[0]["duration_min"] == 30
        assert blocks[1]["duration_min"] == 60

    def test_empty_segments(self):
        """Empty segment list -> no blocks."""
        blocks = _extract_focus_blocks_from_segments([])
        assert len(blocks) == 0

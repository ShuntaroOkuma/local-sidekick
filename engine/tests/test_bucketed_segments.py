"""Tests for build_bucketed_segments()."""

import pytest

from engine.history.aggregator import build_bucketed_segments


def _make_log(timestamp: float, state: str = "focused") -> dict:
    """Create a minimal state log entry."""
    return {
        "timestamp": timestamp,
        "integrated_state": state,
        "camera_state": None,
        "pc_state": None,
        "confidence": 1.0,
    }


# Use a base timestamp aligned to a 5-min boundary: 2024-02-14 00:00:00 UTC
BASE_TS = 1707868800.0  # aligned to bucket boundary


class TestEmptyAndSingle:
    def test_empty_logs(self):
        assert build_bucketed_segments([]) == []

    def test_single_entry(self):
        logs = [_make_log(BASE_TS, "focused")]
        result = build_bucketed_segments(logs)
        assert len(result) == 1
        assert result[0]["state"] == "focused"
        assert result[0]["start_time"] == BASE_TS
        assert result[0]["end_time"] == BASE_TS + 300
        assert result[0]["duration_min"] == 5.0
        assert "focused" in result[0]["breakdown"]


class TestMajorityVote:
    def test_majority_vote_focused(self):
        """Within one bucket, focused has most total duration -> state=focused."""
        logs = [
            _make_log(BASE_TS + 0, "focused"),
            _make_log(BASE_TS + 10, "focused"),
            _make_log(BASE_TS + 20, "focused"),
            _make_log(BASE_TS + 30, "distracted"),
        ]
        result = build_bucketed_segments(logs)
        assert len(result) == 1
        assert result[0]["state"] == "focused"

    def test_majority_vote_distracted(self):
        """Within one bucket, distracted has most total duration -> state=distracted."""
        logs = [
            _make_log(BASE_TS + 0, "distracted"),
            _make_log(BASE_TS + 10, "distracted"),
            _make_log(BASE_TS + 20, "distracted"),
            _make_log(BASE_TS + 30, "focused"),
        ]
        result = build_bucketed_segments(logs)
        assert len(result) == 1
        assert result[0]["state"] == "distracted"


class TestMerging:
    def test_merge_consecutive_same_state(self):
        """Two consecutive buckets with same dominant state -> merged into 1 segment."""
        logs = [
            # Bucket 1: 0:00-0:05 -> focused
            _make_log(BASE_TS + 0, "focused"),
            _make_log(BASE_TS + 10, "focused"),
            # Bucket 2: 0:05-0:10 -> focused
            _make_log(BASE_TS + 300, "focused"),
            _make_log(BASE_TS + 310, "focused"),
        ]
        result = build_bucketed_segments(logs)
        assert len(result) == 1
        assert result[0]["state"] == "focused"
        assert result[0]["start_time"] == BASE_TS
        assert result[0]["end_time"] == BASE_TS + 600
        assert result[0]["duration_min"] == 10.0

    def test_different_states_no_merge(self):
        """Two consecutive buckets with different states -> 2 segments."""
        logs = [
            # Bucket 1: focused
            _make_log(BASE_TS + 0, "focused"),
            _make_log(BASE_TS + 10, "focused"),
            # Bucket 2: distracted
            _make_log(BASE_TS + 300, "distracted"),
            _make_log(BASE_TS + 310, "distracted"),
        ]
        result = build_bucketed_segments(logs)
        assert len(result) == 2
        assert result[0]["state"] == "focused"
        assert result[1]["state"] == "distracted"


class TestGaps:
    def test_gap_splits_segments(self):
        """A gap (missing bucket) between two same-state buckets -> 2 segments."""
        logs = [
            # Bucket at BASE_TS (0:00-0:05)
            _make_log(BASE_TS + 0, "focused"),
            # Gap: no data for 0:05-0:10
            # Bucket at BASE_TS+600 (0:10-0:15)
            _make_log(BASE_TS + 600, "focused"),
        ]
        result = build_bucketed_segments(logs)
        assert len(result) == 2
        assert result[0]["end_time"] == BASE_TS + 300
        assert result[1]["start_time"] == BASE_TS + 600


class TestBreakdown:
    def test_breakdown_accuracy(self):
        """Breakdown should sum durations per state correctly."""
        logs = [
            _make_log(BASE_TS + 0, "focused"),    # duration=10s
            _make_log(BASE_TS + 10, "distracted"),  # duration=10s
            _make_log(BASE_TS + 20, "focused"),    # duration=10s
            _make_log(BASE_TS + 30, "focused"),    # duration=5s (last entry)
        ]
        result = build_bucketed_segments(logs)
        assert len(result) == 1
        bd = result[0]["breakdown"]
        assert bd["focused"] == pytest.approx(25.0)  # 10 + 10 + 5
        assert bd["distracted"] == pytest.approx(10.0)


class TestParameters:
    def test_max_entry_duration_capping(self):
        """Entries with gap > 30s should be capped at max_entry_duration."""
        logs = [
            _make_log(BASE_TS + 0, "focused"),    # gap to next = 120s, capped at 30s
            _make_log(BASE_TS + 120, "focused"),   # last entry = 5s
        ]
        result = build_bucketed_segments(logs)
        # Both entries in same bucket (BASE_TS)
        assert len(result) == 1
        total = sum(result[0]["breakdown"].values())
        assert total == pytest.approx(35.0)  # 30 + 5

    def test_custom_bucket_minutes(self):
        """bucket_minutes=10 should use 10-minute buckets."""
        logs = [
            # These are in the same 10-min bucket but different 5-min buckets
            _make_log(BASE_TS + 0, "focused"),
            _make_log(BASE_TS + 300, "focused"),
        ]
        result = build_bucketed_segments(logs, bucket_minutes=10)
        assert len(result) == 1
        assert result[0]["duration_min"] == 10.0
        assert result[0]["end_time"] - result[0]["start_time"] == 600

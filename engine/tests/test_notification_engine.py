"""Tests for bucket-based NotificationEngine."""

import pytest

from engine.notification.engine import NotificationEngine


def _make_segment(state: str, duration_min: float = 5.0, start_time: float = 0.0) -> dict:
    """Create a minimal bucketed segment."""
    return {
        "state": state,
        "start_time": start_time,
        "end_time": start_time + duration_min * 60,
        "duration_min": duration_min,
        "breakdown": {state: duration_min * 60},
    }


NOW = 1707900000.0  # arbitrary fixed timestamp for tests


class TestDrowsy:
    def test_two_consecutive_drowsy_triggers(self):
        """Last 2 buckets drowsy -> notification fires."""
        engine = NotificationEngine(drowsy_trigger_buckets=2)
        segments = [
            _make_segment("focused", 5.0, 0),
            _make_segment("drowsy", 10.0, 300),  # 2 buckets worth
        ]
        result = engine.check_buckets(segments, NOW)
        assert result is not None
        assert result.type == "drowsy"

    def test_one_drowsy_bucket_not_enough(self):
        """Only 1 drowsy bucket -> no notification."""
        engine = NotificationEngine(drowsy_trigger_buckets=2)
        segments = [
            _make_segment("focused", 5.0, 0),
            _make_segment("drowsy", 5.0, 300),  # 1 bucket
        ]
        result = engine.check_buckets(segments, NOW)
        assert result is None

    def test_drowsy_interrupted_by_focused(self):
        """Drowsy, then focused, then drowsy -> not consecutive, no notification."""
        engine = NotificationEngine(drowsy_trigger_buckets=2)
        segments = [
            _make_segment("drowsy", 5.0, 0),
            _make_segment("focused", 5.0, 300),
            _make_segment("drowsy", 5.0, 600),
        ]
        result = engine.check_buckets(segments, NOW)
        assert result is None


class TestDistracted:
    def test_two_consecutive_distracted_triggers(self):
        """Last 2 buckets distracted -> notification fires."""
        engine = NotificationEngine(distracted_trigger_buckets=2)
        segments = [
            _make_segment("focused", 5.0, 0),
            _make_segment("distracted", 10.0, 300),  # 2 buckets
        ]
        result = engine.check_buckets(segments, NOW)
        assert result is not None
        assert result.type == "distracted"

    def test_one_distracted_not_enough(self):
        """Only 1 distracted bucket -> no notification."""
        engine = NotificationEngine(distracted_trigger_buckets=2)
        segments = [
            _make_segment("distracted", 5.0, 0),
        ]
        result = engine.check_buckets(segments, NOW)
        assert result is None


class TestOverFocus:
    def test_over_focus_triggers(self):
        """17 out of 18 buckets focused (above threshold) -> over_focus fires."""
        engine = NotificationEngine(
            over_focus_window_buckets=18,
            over_focus_threshold_buckets=16,
        )
        # Use "away" for non-focused buckets to avoid triggering drowsy/distracted
        segments = [
            _make_segment("focused", 85.0, 0),  # 17 buckets
            _make_segment("away", 5.0, 5100),    # 1 bucket
        ]
        result = engine.check_buckets(segments, NOW)
        assert result is not None
        assert result.type == "over_focus"

    def test_over_focus_below_threshold(self):
        """15 out of 18 buckets focused -> no notification."""
        engine = NotificationEngine(
            over_focus_window_buckets=18,
            over_focus_threshold_buckets=16,
        )
        segments = [
            _make_segment("focused", 75.0, 0),  # 15 buckets
            _make_segment("away", 15.0, 4500),   # 3 buckets
        ]
        result = engine.check_buckets(segments, NOW)
        assert result is None

    def test_over_focus_exact_threshold(self):
        """Exactly 16 out of 18 buckets -> fires."""
        engine = NotificationEngine(
            over_focus_window_buckets=18,
            over_focus_threshold_buckets=16,
        )
        # 16 focused + 2 away = 18 buckets total
        segments = [
            _make_segment("focused", 80.0, 0),    # 16 buckets
            _make_segment("away", 10.0, 4800),     # 2 buckets
        ]
        result = engine.check_buckets(segments, NOW)
        assert result is not None
        assert result.type == "over_focus"


class TestCooldown:
    def test_cooldown_prevents_duplicate(self):
        """After a drowsy notification, same check within cooldown -> no notification."""
        engine = NotificationEngine(
            drowsy_trigger_buckets=2,
            drowsy_cooldown_minutes=15,
        )
        segments = [_make_segment("drowsy", 10.0, 0)]  # 2 buckets

        # First call triggers
        result1 = engine.check_buckets(segments, NOW)
        assert result1 is not None

        # Second call within cooldown (1 minute later) -> None
        result2 = engine.check_buckets(segments, NOW + 60)
        assert result2 is None

    def test_cooldown_expires(self):
        """After cooldown expires, notification fires again."""
        engine = NotificationEngine(
            drowsy_trigger_buckets=2,
            drowsy_cooldown_minutes=15,
        )
        segments = [_make_segment("drowsy", 10.0, 0)]

        result1 = engine.check_buckets(segments, NOW)
        assert result1 is not None

        # After cooldown (16 minutes later) -> fires again
        result2 = engine.check_buckets(segments, NOW + 16 * 60)
        assert result2 is not None


class TestReset:
    def test_reset_clears_cooldown(self):
        """reset() clears cooldown timers."""
        engine = NotificationEngine(
            drowsy_trigger_buckets=2,
            drowsy_cooldown_minutes=15,
        )
        segments = [_make_segment("drowsy", 10.0, 0)]

        result1 = engine.check_buckets(segments, NOW)
        assert result1 is not None

        # Within cooldown -> None
        result2 = engine.check_buckets(segments, NOW + 60)
        assert result2 is None

        # After reset -> fires again
        engine.reset()
        result3 = engine.check_buckets(segments, NOW + 60)
        assert result3 is not None


class TestEmptyInput:
    def test_empty_segments(self):
        """Empty segments -> no notification."""
        engine = NotificationEngine()
        result = engine.check_buckets([], NOW)
        assert result is None

    def test_single_focused_segment(self):
        """Just one focused segment -> no drowsy/distracted notification."""
        engine = NotificationEngine()
        segments = [_make_segment("focused", 5.0, 0)]
        result = engine.check_buckets(segments, NOW)
        assert result is None


class TestPriority:
    def test_drowsy_checked_before_distracted(self):
        """When both drowsy and distracted conditions met, drowsy wins (checked first)."""
        engine = NotificationEngine(
            drowsy_trigger_buckets=2,
            distracted_trigger_buckets=2,
        )
        # This shouldn't happen in practice (a segment is one state),
        # but verify priority order with sequential segments
        segments = [
            _make_segment("distracted", 10.0, 0),
            _make_segment("drowsy", 10.0, 600),
        ]
        result = engine.check_buckets(segments, NOW)
        # Last 2 buckets are drowsy, so drowsy fires
        assert result is not None
        assert result.type == "drowsy"

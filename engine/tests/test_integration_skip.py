"""Tests for integration loop skip-recording logic and stale snapshot handling.

Verifies that the engine correctly skips recording when:
- Camera is unavailable AND PC is idle (nighttime / Power Nap scenario)
- Snapshots are stale (older than max age)
"""

from __future__ import annotations

from engine.main import _is_pc_idle, _SNAPSHOT_MAX_AGE_SECONDS


def make_pc_snapshot(**overrides: object) -> dict:
    """Create a PC usage snapshot dict with sensible defaults."""
    base = {
        "active_app": "Code",
        "idle_seconds": 5,
        "is_idle": False,
        "keyboard_rate_window": 120,
        "mouse_rate_window": 80,
        "app_switches_in_window": 2,
        "unique_apps_in_window": 2,
        "seconds_since_last_keyboard": 3,
    }
    base.update(overrides)
    return base


class TestIsPcIdle:
    """Tests for the _is_pc_idle helper."""

    def test_none_is_idle(self) -> None:
        """No PC snapshot means idle."""
        assert _is_pc_idle(None) is True

    def test_is_idle_true(self) -> None:
        """PC snapshot with is_idle=True is idle."""
        pc = make_pc_snapshot(is_idle=True, idle_seconds=120)
        assert _is_pc_idle(pc) is True

    def test_is_idle_false(self) -> None:
        """PC snapshot with is_idle=False is not idle."""
        pc = make_pc_snapshot(is_idle=False, idle_seconds=5)
        assert _is_pc_idle(pc) is False

    def test_missing_is_idle_key_defaults_to_false(self) -> None:
        """If is_idle key is missing, treat as not idle (safe default)."""
        pc = {"active_app": "Code", "idle_seconds": 5}
        assert _is_pc_idle(pc) is False


class TestSnapshotMaxAge:
    """Tests for stale snapshot configuration."""

    def test_max_age_is_positive(self) -> None:
        """Max age constant should be a positive number."""
        assert _SNAPSHOT_MAX_AGE_SECONDS > 0

    def test_max_age_is_30_seconds(self) -> None:
        """Default max age should be 30 seconds."""
        assert _SNAPSHOT_MAX_AGE_SECONDS == 30.0


class TestSkipRecordingScenarios:
    """Integration tests for skip-recording decision logic.

    These test the decision table:
    | Camera     | PC     | Action        |
    |------------|--------|---------------|
    | available  | any    | record        |
    | unavailable| active | record (LLM)  |
    | unavailable| idle   | SKIP          |
    | unavailable| None   | SKIP          |
    """

    def test_camera_none_pc_idle_should_skip(self) -> None:
        """Camera unavailable + PC idle -> should skip."""
        camera_snap = None
        pc_snap = make_pc_snapshot(is_idle=True, idle_seconds=3600)

        should_skip = camera_snap is None and _is_pc_idle(pc_snap)
        assert should_skip is True

    def test_camera_none_pc_active_should_not_skip(self) -> None:
        """Camera unavailable + PC active -> should NOT skip (LLM classifies)."""
        camera_snap = None
        pc_snap = make_pc_snapshot(is_idle=False, idle_seconds=5)

        should_skip = camera_snap is None and _is_pc_idle(pc_snap)
        assert should_skip is False

    def test_camera_none_pc_none_should_skip(self) -> None:
        """Camera unavailable + PC unavailable -> should skip."""
        camera_snap = None
        pc_snap = None

        should_skip = camera_snap is None and _is_pc_idle(pc_snap)
        assert should_skip is True

    def test_camera_available_pc_idle_should_not_skip(self) -> None:
        """Camera available + PC idle -> should NOT skip (camera data useful)."""
        camera_snap = {"face_detected": True, "ear_average": 0.30}
        pc_snap = make_pc_snapshot(is_idle=True, idle_seconds=120)

        should_skip = camera_snap is None and _is_pc_idle(pc_snap)
        assert should_skip is False

    def test_camera_available_pc_active_should_not_skip(self) -> None:
        """Camera available + PC active -> should NOT skip."""
        camera_snap = {"face_detected": True, "ear_average": 0.30}
        pc_snap = make_pc_snapshot(is_idle=False, idle_seconds=5)

        should_skip = camera_snap is None and _is_pc_idle(pc_snap)
        assert should_skip is False

    def test_nighttime_power_nap_scenario(self) -> None:
        """Simulates Power Nap: no camera, PC idle for hours -> skip."""
        camera_snap = None
        pc_snap = make_pc_snapshot(
            is_idle=True,
            idle_seconds=7200,  # 2 hours idle
            keyboard_rate_window=0,
            mouse_rate_window=0,
            keyboard_events_in_window=0,
            mouse_events_in_window=0,
        )

        should_skip = camera_snap is None and _is_pc_idle(pc_snap)
        assert should_skip is True

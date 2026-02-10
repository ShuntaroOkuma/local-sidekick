"""PC usage monitoring for macOS.

Collects active application, keyboard/mouse event counts, and idle time.
CRITICAL: Never records keyboard/mouse content - only event counts.

Usage:
    python -m experiment3_pcusage.monitor --duration 30
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class UsageSnapshot:
    """Immutable snapshot of PC usage at a point in time."""

    timestamp: float
    active_app: str
    idle_seconds: float
    keyboard_events_total: int
    mouse_events_total: int
    keyboard_events_per_min: float
    mouse_events_per_min: float
    app_switches_in_window: int
    unique_apps_in_window: int
    app_history_window: tuple[str, ...]
    keyboard_events_in_window: int = 0
    mouse_events_in_window: int = 0
    keyboard_rate_window: float = 0.0
    mouse_rate_window: float = 0.0
    seconds_since_last_keyboard: float = 0.0
    seconds_since_last_mouse: float = 0.0
    is_idle: bool = False

    def to_dict(self) -> dict:
        """Convert to a plain dict for JSON serialization."""
        result = asdict(self)
        result["app_history_window"] = list(self.app_history_window)
        return result


@dataclass
class _LegacyCounters:
    """Internal mutable state for event counting (thread-safe via lock)."""

    keyboard_count: int = 0
    mouse_count: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def increment_keyboard(self) -> None:
        with self.lock:
            self.keyboard_count += 1

    def increment_mouse(self) -> None:
        with self.lock:
            self.mouse_count += 1

    def read(self) -> tuple[int, int]:
        with self.lock:
            return self.keyboard_count, self.mouse_count


@dataclass
class _WindowedCounters:
    """Windowed event counting with timestamp-based deques (thread-safe)."""

    window_seconds: float = 60.0
    _keyboard_times: deque = field(default_factory=deque)
    _mouse_click_times: deque = field(default_factory=deque)
    _mouse_move_times: deque = field(default_factory=deque)
    _last_mouse_move_time: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record_keyboard(self) -> None:
        with self._lock:
            self._keyboard_times.append(time.time())

    def record_mouse_click(self) -> None:
        with self._lock:
            self._mouse_click_times.append(time.time())

    def record_mouse_move(self) -> None:
        now = time.time()
        with self._lock:
            # Throttle mouse moves to max 10/sec to avoid flooding
            if now - self._last_mouse_move_time < 0.1:
                return
            self._last_mouse_move_time = now
            self._mouse_move_times.append(now)

    def _prune(self, q: deque, now: float) -> None:
        cutoff = now - self.window_seconds
        while q and q[0] < cutoff:
            q.popleft()

    def get_windowed_stats(self, now: float) -> dict:
        with self._lock:
            self._prune(self._keyboard_times, now)
            self._prune(self._mouse_click_times, now)
            self._prune(self._mouse_move_times, now)
            kb_count = len(self._keyboard_times)
            mouse_click_count = len(self._mouse_click_times)
            mouse_move_count = len(self._mouse_move_times)
            mouse_total = mouse_click_count + mouse_move_count
            window_min = self.window_seconds / 60.0
            return {
                "keyboard_events_in_window": kb_count,
                "mouse_events_in_window": mouse_total,
                "keyboard_rate_window": round(kb_count / window_min, 1),
                "mouse_rate_window": round(mouse_total / window_min, 1),
                "last_keyboard_time": self._keyboard_times[-1] if self._keyboard_times else 0.0,
                "last_mouse_time": max(
                    self._mouse_click_times[-1] if self._mouse_click_times else 0.0,
                    self._mouse_move_times[-1] if self._mouse_move_times else 0.0,
                ),
            }

    def get_totals(self) -> tuple[int, int]:
        with self._lock:
            return (
                len(self._keyboard_times),
                len(self._mouse_click_times) + len(self._mouse_move_times),
            )


def _check_accessibility_permission() -> bool:
    """Check if the app has accessibility / input monitoring permission."""
    try:
        from Quartz import (
            CGEventSourceSecondsSinceLastEventType,
            kCGEventSourceStateCombinedSessionState,
            kCGEventKeyDown,
        )

        CGEventSourceSecondsSinceLastEventType(
            kCGEventSourceStateCombinedSessionState,
            kCGEventKeyDown,
        )
        return True
    except Exception:
        return False


def _check_pynput_permission() -> bool:
    """Check if pynput can start listeners (requires Input Monitoring)."""
    try:
        from pynput import keyboard

        def on_press(_key: object) -> None:
            pass

        listener = keyboard.Listener(on_press=on_press)
        listener.start()
        time.sleep(0.2)
        alive = listener.is_alive()
        listener.stop()
        return alive
    except Exception:
        return False


def get_active_app() -> str:
    """Get the name of the frontmost application using NSWorkspace.

    Returns 'Unknown' if detection fails.
    """
    try:
        from AppKit import NSWorkspace

        workspace = NSWorkspace.sharedWorkspace()
        active = workspace.frontmostApplication()
        name = active.localizedName()
        return str(name) if name else "Unknown"
    except Exception:
        return "Unknown"


def get_idle_seconds() -> float:
    """Get seconds since last user input event using CGEventSource.

    Returns 0.0 if detection fails.
    """
    try:
        from Quartz import (
            CGEventSourceSecondsSinceLastEventType,
            kCGEventSourceStateCombinedSessionState,
            kCGAnyInputEventType,
        )

        idle = CGEventSourceSecondsSinceLastEventType(
            kCGEventSourceStateCombinedSessionState,
            kCGAnyInputEventType,
        )
        return max(0.0, float(idle))
    except Exception:
        return 0.0


class PCUsageMonitor:
    """Monitors PC usage: active app, input events, idle time.

    PRIVACY: Only counts keyboard/mouse events. Never records content.
    """

    def __init__(self, window_seconds: int = 60) -> None:
        self._window_seconds = window_seconds
        self._counters = _WindowedCounters(window_seconds=float(window_seconds))
        self._app_history: deque[tuple[float, str]] = deque()
        self._start_time: float | None = None
        self._keyboard_listener: object | None = None
        self._mouse_listener: object | None = None
        self._running = False
        self._last_app: str = ""
        self._app_poll_thread: threading.Thread | None = None

    def check_permissions(self) -> dict[str, bool]:
        """Check required macOS permissions and return status."""
        results = {
            "nsworkspace": False,
            "cgevent_source": False,
            "input_monitoring": False,
        }

        # NSWorkspace - no special permission needed
        try:
            app = get_active_app()
            results["nsworkspace"] = app != "Unknown"
        except Exception:
            pass

        # CGEventSource - no special permission needed
        results["cgevent_source"] = _check_accessibility_permission()

        # Input Monitoring - requires System Settings permission
        results["input_monitoring"] = _check_pynput_permission()

        return results

    def print_permission_guidance(self, permissions: dict[str, bool]) -> None:
        """Print guidance for missing permissions."""
        all_ok = all(permissions.values())
        if all_ok:
            print("[OK] All permissions granted.")
            return

        print("\n[WARNING] Some permissions are missing:\n")
        if not permissions["nsworkspace"]:
            print("  - NSWorkspace: Unable to detect active application.")
            print("    This should work without special permissions.")
            print("    Try running from Terminal.app directly.\n")

        if not permissions["cgevent_source"]:
            print("  - CGEventSource: Unable to detect idle time.")
            print("    Try granting Accessibility permission:\n")
            print(
                "    System Settings > Privacy & Security > Accessibility"
            )
            print("    Add your terminal app (e.g., Terminal.app)\n")

        if not permissions["input_monitoring"]:
            print("  - Input Monitoring: Unable to count keyboard/mouse events.")
            print("    Grant Input Monitoring permission:\n")
            print(
                "    System Settings > Privacy & Security > Input Monitoring"
            )
            print("    Add your terminal app (e.g., Terminal.app)")
            print("    You may need to restart your terminal after granting.\n")

    def _start_app_polling(self, poll_interval: float = 2.0) -> None:
        """Poll active app in background to catch switches between snapshots."""
        def poll_loop() -> None:
            while self._running:
                now = time.time()
                current_app = get_active_app()
                self._update_app_history(now, current_app)
                time.sleep(poll_interval)

        self._app_poll_thread = threading.Thread(target=poll_loop, daemon=True)
        self._app_poll_thread.start()

    def start(self) -> None:
        """Start monitoring. Call stop() to clean up."""
        if self._running:
            return

        self._start_time = time.time()
        self._running = True
        self._start_input_listeners()
        self._start_app_polling()

    def stop(self) -> None:
        """Stop monitoring and clean up listeners."""
        self._running = False
        self._stop_input_listeners()

    def _start_input_listeners(self) -> None:
        """Start pynput listeners for keyboard and mouse event counting."""
        try:
            from pynput import keyboard, mouse

            def on_key_press(_key: object) -> None:
                self._counters.record_keyboard()

            def on_mouse_click(
                _x: object, _y: object, _button: object, pressed: bool
            ) -> None:
                if pressed:
                    self._counters.record_mouse_click()

            def on_mouse_scroll(
                _x: object, _y: object, _dx: object, _dy: object
            ) -> None:
                self._counters.record_mouse_click()

            def on_mouse_move(_x: object, _y: object) -> None:
                self._counters.record_mouse_move()

            self._keyboard_listener = keyboard.Listener(on_press=on_key_press)
            self._mouse_listener = mouse.Listener(
                on_click=on_mouse_click,
                on_scroll=on_mouse_scroll,
                on_move=on_mouse_move,
            )
            self._keyboard_listener.start()
            self._mouse_listener.start()
        except Exception as e:
            print(f"[WARNING] Failed to start input listeners: {e}")
            print("  Keyboard/mouse event counting will be unavailable.")

    def _stop_input_listeners(self) -> None:
        """Stop pynput listeners gracefully."""
        if self._keyboard_listener is not None:
            try:
                self._keyboard_listener.stop()
            except Exception:
                pass
            self._keyboard_listener = None

        if self._mouse_listener is not None:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
            self._mouse_listener = None

    def _update_app_history(self, now: float, current_app: str) -> None:
        """Track app switches in the sliding window."""
        if current_app != self._last_app:
            self._app_history.append((now, current_app))
            self._last_app = current_app

        # Prune entries outside the window
        cutoff = now - self._window_seconds
        while self._app_history and self._app_history[0][0] < cutoff:
            self._app_history.popleft()

    def take_snapshot(self) -> UsageSnapshot:
        """Capture current usage state as an immutable snapshot."""
        now = time.time()
        elapsed = now - self._start_time if self._start_time else 0.0
        elapsed_minutes = max(elapsed / 60.0, 1.0 / 60.0)  # avoid division by zero

        current_app = get_active_app()
        idle_seconds = get_idle_seconds()
        keyboard_total, mouse_total = self._counters.get_totals()

        self._update_app_history(now, current_app)

        # Compute windowed stats
        apps_in_window = [app for _, app in self._app_history]
        app_switches = max(0, len(apps_in_window) - 1)
        unique_apps = len(set(apps_in_window))

        windowed = self._counters.get_windowed_stats(now)
        seconds_since_last_keyboard = (
            now - windowed["last_keyboard_time"]
            if windowed["last_keyboard_time"] > 0 else elapsed
        )
        seconds_since_last_mouse = (
            now - windowed["last_mouse_time"]
            if windowed["last_mouse_time"] > 0 else elapsed
        )
        is_idle = idle_seconds > 30.0

        return UsageSnapshot(
            timestamp=now,
            active_app=current_app,
            idle_seconds=round(idle_seconds, 1),
            keyboard_events_total=keyboard_total,
            mouse_events_total=mouse_total,
            keyboard_events_per_min=round(keyboard_total / elapsed_minutes, 1),
            mouse_events_per_min=round(mouse_total / elapsed_minutes, 1),
            app_switches_in_window=app_switches,
            unique_apps_in_window=unique_apps,
            app_history_window=tuple(apps_in_window[-10:]),
            keyboard_events_in_window=windowed["keyboard_events_in_window"],
            mouse_events_in_window=windowed["mouse_events_in_window"],
            keyboard_rate_window=windowed["keyboard_rate_window"],
            mouse_rate_window=windowed["mouse_rate_window"],
            seconds_since_last_keyboard=round(seconds_since_last_keyboard, 1),
            seconds_since_last_mouse=round(seconds_since_last_mouse, 1),
            is_idle=is_idle,
        )


def run_cli(duration: int, interval: float) -> list[dict]:
    """Run the monitor in CLI mode, printing snapshots at each interval."""
    monitor = PCUsageMonitor(window_seconds=60)

    # Check permissions first
    print("Checking macOS permissions...")
    permissions = monitor.check_permissions()
    monitor.print_permission_guidance(permissions)

    if not permissions["nsworkspace"]:
        print("\n[ERROR] Cannot detect active application. Aborting.")
        return []

    print(f"\nStarting PC usage monitor for {duration}s (interval: {interval}s)")
    print("Press Ctrl+C to stop early.\n")

    # Handle graceful shutdown
    stop_event = threading.Event()

    def signal_handler(_sig: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)

    snapshots: list[dict] = []
    monitor.start()

    try:
        start = time.time()
        while not stop_event.is_set():
            elapsed = time.time() - start
            if elapsed >= duration:
                break

            snapshot = monitor.take_snapshot()
            snapshot_dict = snapshot.to_dict()
            snapshots.append(snapshot_dict)

            print(f"[{elapsed:.0f}s] {json.dumps(snapshot_dict, indent=2)}")
            print()

            # Wait for next interval or stop signal
            stop_event.wait(timeout=interval)
    finally:
        monitor.stop()
        print(f"\nCollected {len(snapshots)} snapshots.")

    return snapshots


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="PC usage monitor - collects active app, input events, idle time",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Duration in seconds (default: 30)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Snapshot interval in seconds (default: 1.0)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for CLI usage."""
    args = parse_args(argv)
    run_cli(duration=args.duration, interval=args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())

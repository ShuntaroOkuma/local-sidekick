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

    def to_dict(self) -> dict:
        """Convert to a plain dict for JSON serialization."""
        result = asdict(self)
        result["app_history_window"] = list(self.app_history_window)
        return result


@dataclass
class _MutableCounters:
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
        self._counters = _MutableCounters()
        self._app_history: deque[tuple[float, str]] = deque()
        self._start_time: float | None = None
        self._keyboard_listener: object | None = None
        self._mouse_listener: object | None = None
        self._running = False
        self._last_app: str = ""

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

    def start(self) -> None:
        """Start monitoring. Call stop() to clean up."""
        if self._running:
            return

        self._start_time = time.time()
        self._running = True
        self._start_input_listeners()

    def stop(self) -> None:
        """Stop monitoring and clean up listeners."""
        self._running = False
        self._stop_input_listeners()

    def _start_input_listeners(self) -> None:
        """Start pynput listeners for keyboard and mouse event counting."""
        try:
            from pynput import keyboard, mouse

            def on_key_press(_key: object) -> None:
                self._counters.increment_keyboard()

            def on_mouse_click(
                _x: object, _y: object, _button: object, pressed: bool
            ) -> None:
                if pressed:
                    self._counters.increment_mouse()

            def on_mouse_scroll(
                _x: object, _y: object, _dx: object, _dy: object
            ) -> None:
                self._counters.increment_mouse()

            def on_mouse_move(_x: object, _y: object) -> None:
                self._counters.increment_mouse()

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
        keyboard_total, mouse_total = self._counters.read()

        self._update_app_history(now, current_app)

        # Compute windowed stats
        apps_in_window = [app for _, app in self._app_history]
        app_switches = max(0, len(apps_in_window) - 1)
        unique_apps = len(set(apps_in_window))

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

"""Notification engine for drowsy/distracted/over-focus alerts.

Implements three notification types with cooldown and daily limits:
- drowsy: continuous drowsy state for 120s, cooldown 15min
- distracted: continuous distracted state for 120s, cooldown 20min
- over_focus: 80+ minutes focused in last 90 minutes, cooldown 30min
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Notification:
    """A triggered notification."""

    type: str  # drowsy, distracted, over_focus
    message: str
    timestamp: float
    user_action: Optional[str] = None  # accepted, snoozed, dismissed


# Default messages for each notification type
_MESSAGES = {
    "drowsy": "Drowsiness detected. Consider taking a short break or stretching.",
    "distracted": "You seem distracted. Try focusing on one task at a time.",
    "over_focus": "You have been focused for over 80 minutes. Take a 5-minute break.",
}


class NotificationEngine:
    """Evaluates state history and triggers notifications with cooldown.

    Args:
        drowsy_trigger_seconds: Consecutive drowsy seconds to trigger notification.
        distracted_trigger_seconds: Consecutive distracted seconds to trigger.
        over_focus_window_minutes: Window to check focused time.
        over_focus_threshold_minutes: Focused minutes in window to trigger.
        drowsy_cooldown_minutes: Cooldown after drowsy notification.
        distracted_cooldown_minutes: Cooldown after distracted notification.
        over_focus_cooldown_minutes: Cooldown after over_focus notification.
        max_notifications_per_day: Maximum notifications per calendar day.
    """

    def __init__(
        self,
        drowsy_trigger_seconds: int = 120,
        distracted_trigger_seconds: int = 120,
        over_focus_window_minutes: int = 90,
        over_focus_threshold_minutes: int = 80,
        drowsy_cooldown_minutes: int = 15,
        distracted_cooldown_minutes: int = 20,
        over_focus_cooldown_minutes: int = 30,
        max_notifications_per_day: int = 6,
    ) -> None:
        self._drowsy_trigger = drowsy_trigger_seconds
        self._distracted_trigger = distracted_trigger_seconds
        self._over_focus_window = over_focus_window_minutes * 60  # seconds
        self._over_focus_threshold = over_focus_threshold_minutes * 60  # seconds
        self._cooldowns = {
            "drowsy": drowsy_cooldown_minutes * 60,
            "distracted": distracted_cooldown_minutes * 60,
            "over_focus": over_focus_cooldown_minutes * 60,
        }
        self._max_per_day = max_notifications_per_day

        # State tracking
        self._consecutive_state: Optional[str] = None
        self._consecutive_start: float = 0.0
        self._last_notification_time: dict[str, float] = {}
        self._today_count: int = 0
        self._today_date: Optional[str] = None

        # History of states for over_focus calculation
        # Stores (timestamp, state, duration_seconds)
        self._state_history: deque[tuple[float, str, float]] = deque()

        # All notifications triggered
        self.notifications: list[Notification] = []

    def _reset_day_if_needed(self, now: float) -> None:
        """Reset daily counter if the date has changed."""
        import datetime
        today = datetime.date.today().isoformat()
        if self._today_date != today:
            self._today_date = today
            self._today_count = 0

    def _is_on_cooldown(self, notification_type: str, now: float) -> bool:
        """Check if a notification type is still on cooldown."""
        last_time = self._last_notification_time.get(notification_type, 0.0)
        cooldown = self._cooldowns.get(notification_type, 0)
        return (now - last_time) < cooldown

    def _can_notify(self, notification_type: str, now: float) -> bool:
        """Check if we can send a notification (cooldown + daily limit)."""
        self._reset_day_if_needed(now)
        if self._today_count >= self._max_per_day:
            return False
        if self._is_on_cooldown(notification_type, now):
            return False
        return True

    def _trigger(self, notification_type: str, now: float) -> Notification:
        """Create and record a notification."""
        notification = Notification(
            type=notification_type,
            message=_MESSAGES.get(notification_type, ""),
            timestamp=now,
        )
        self._last_notification_time[notification_type] = now
        self._today_count += 1
        self.notifications.append(notification)
        logger.info(
            "Notification triggered: %s (total today: %d)",
            notification_type,
            self._today_count,
        )
        return notification

    def _check_over_focus(self, now: float) -> Optional[Notification]:
        """Check if focused time in the window exceeds the threshold."""
        if not self._can_notify("over_focus", now):
            return None

        window_start = now - self._over_focus_window
        focused_seconds = 0.0

        for ts, state, duration in self._state_history:
            if ts < window_start:
                continue
            if state == "focused":
                focused_seconds += duration

        if focused_seconds >= self._over_focus_threshold:
            return self._trigger("over_focus", now)

        return None

    def evaluate(
        self,
        state: str,
        timestamp: float,
        interval_seconds: float = 5.0,
    ) -> Optional[Notification]:
        """Evaluate the current state and return a notification if triggered.

        Should be called at each integration interval with the current state.

        Args:
            state: Current integrated state (focused/drowsy/distracted/away).
            timestamp: Current timestamp.
            interval_seconds: Time since last evaluation.

        Returns:
            A Notification if one was triggered, or None.
        """
        now = timestamp

        # Record state for over_focus tracking
        self._state_history.append((now, state, interval_seconds))

        # Prune old entries (keep 2x the over_focus window)
        cutoff = now - self._over_focus_window * 2
        while self._state_history and self._state_history[0][0] < cutoff:
            self._state_history.popleft()

        # Track consecutive state
        if state != self._consecutive_state:
            self._consecutive_state = state
            self._consecutive_start = now

        consecutive_seconds = now - self._consecutive_start

        # Check drowsy
        if state == "drowsy" and consecutive_seconds >= self._drowsy_trigger:
            if self._can_notify("drowsy", now):
                return self._trigger("drowsy", now)

        # Check distracted
        if state == "distracted" and consecutive_seconds >= self._distracted_trigger:
            if self._can_notify("distracted", now):
                return self._trigger("distracted", now)

        # Check over_focus
        over_focus = self._check_over_focus(now)
        if over_focus is not None:
            return over_focus

        return None

    def reset_consecutive(self) -> None:
        """Reset consecutive state tracking (e.g. after system resume).

        Prevents sleep/pause duration from counting toward
        distracted or drowsy notification thresholds.
        """
        self._consecutive_state = None
        self._consecutive_start = 0.0

    def record_user_action(
        self,
        notification_index: int,
        action: str,
    ) -> None:
        """Record user response to a notification.

        Args:
            notification_index: Index into self.notifications.
            action: One of "accepted", "snoozed", "dismissed".
        """
        if 0 <= notification_index < len(self.notifications):
            old = self.notifications[notification_index]
            self.notifications[notification_index] = Notification(
                type=old.type,
                message=old.message,
                timestamp=old.timestamp,
                user_action=action,
            )

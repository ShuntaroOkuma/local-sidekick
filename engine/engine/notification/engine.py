"""Notification engine for drowsy/distracted/over-focus alerts.

Uses 5-minute bucketed segments (from build_bucketed_segments) to evaluate
notification conditions. Stateless except for cooldown timers.

Notification types:
- drowsy: last N consecutive buckets are all drowsy, cooldown 15min
- distracted: last N consecutive buckets are all distracted, cooldown 20min
- over_focus: M out of last N buckets are focused, cooldown 30min
"""

from __future__ import annotations

import logging
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
    """Evaluates bucketed segments and triggers notifications with cooldown.

    Args:
        drowsy_trigger_buckets: Consecutive drowsy buckets to trigger notification.
        distracted_trigger_buckets: Consecutive distracted buckets to trigger.
        over_focus_window_buckets: Number of recent buckets to check for over_focus.
        over_focus_threshold_buckets: Focused buckets in window to trigger over_focus.
        drowsy_cooldown_minutes: Cooldown after drowsy notification.
        distracted_cooldown_minutes: Cooldown after distracted notification.
        over_focus_cooldown_minutes: Cooldown after over_focus notification.
    """

    def __init__(
        self,
        drowsy_trigger_buckets: int = 2,
        distracted_trigger_buckets: int = 2,
        over_focus_window_buckets: int = 18,
        over_focus_threshold_buckets: int = 16,
        drowsy_cooldown_minutes: int = 15,
        distracted_cooldown_minutes: int = 20,
        over_focus_cooldown_minutes: int = 30,
    ) -> None:
        self._drowsy_trigger_buckets = drowsy_trigger_buckets
        self._distracted_trigger_buckets = distracted_trigger_buckets
        self._over_focus_window_buckets = over_focus_window_buckets
        self._over_focus_threshold_buckets = over_focus_threshold_buckets
        self._cooldowns = {
            "drowsy": drowsy_cooldown_minutes * 60,
            "distracted": distracted_cooldown_minutes * 60,
            "over_focus": over_focus_cooldown_minutes * 60,
        }

        # Only mutable state: cooldown timers
        self._last_notification_time: dict[str, float] = {}

        # All notifications triggered
        self.notifications: list[Notification] = []

    def _is_on_cooldown(self, notification_type: str, now: float) -> bool:
        """Check if a notification type is still on cooldown."""
        last_time = self._last_notification_time.get(notification_type, 0.0)
        cooldown = self._cooldowns.get(notification_type, 0)
        return (now - last_time) < cooldown

    def _can_notify(self, notification_type: str, now: float) -> bool:
        """Check if we can send a notification (cooldown check)."""
        return not self._is_on_cooldown(notification_type, now)

    def _trigger(self, notification_type: str, now: float) -> Notification:
        """Create and record a notification."""
        notification = Notification(
            type=notification_type,
            message=_MESSAGES.get(notification_type, ""),
            timestamp=now,
        )
        self._last_notification_time[notification_type] = now
        self.notifications.append(notification)
        logger.info("Notification triggered: %s", notification_type)
        return notification

    def check_buckets(
        self,
        segments: list[dict],
        now: float,
    ) -> Optional[Notification]:
        """Evaluate bucketed segments and return a notification if triggered.

        Segments are the output of build_bucketed_segments(), already merged.
        We un-merge them back to per-bucket states to count consecutive/threshold.

        Args:
            segments: Output of build_bucketed_segments().
            now: Current timestamp for cooldown checks.

        Returns:
            A Notification if one was triggered, or None.
        """
        if not segments:
            return None

        # Expand merged segments back to individual 5-min bucket states.
        # Each segment spans duration_min minutes = duration_min/5 buckets.
        bucket_states: list[str] = []
        for seg in segments:
            n_buckets = max(1, round(seg["duration_min"] / 5.0))
            bucket_states.extend([seg["state"]] * n_buckets)

        if not bucket_states:
            return None

        # Check drowsy: last N buckets all drowsy
        if len(bucket_states) >= self._drowsy_trigger_buckets:
            tail = bucket_states[-self._drowsy_trigger_buckets:]
            if all(s == "drowsy" for s in tail):
                if self._can_notify("drowsy", now):
                    return self._trigger("drowsy", now)

        # Check distracted: last N buckets all distracted
        if len(bucket_states) >= self._distracted_trigger_buckets:
            tail = bucket_states[-self._distracted_trigger_buckets:]
            if all(s == "distracted" for s in tail):
                if self._can_notify("distracted", now):
                    return self._trigger("distracted", now)

        # Check over_focus: M out of last N buckets focused
        window = bucket_states[-self._over_focus_window_buckets:]
        focused_count = sum(1 for s in window if s == "focused")
        if focused_count >= self._over_focus_threshold_buckets:
            if self._can_notify("over_focus", now):
                return self._trigger("over_focus", now)

        return None

    def reset(self) -> None:
        """Reset cooldown timers (e.g. after system resume)."""
        self._last_notification_time.clear()

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

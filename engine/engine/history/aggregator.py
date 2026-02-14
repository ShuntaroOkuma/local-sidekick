"""Daily aggregation of state history and notification data.

Computes:
- Total minutes per state (focused, drowsy, distracted, away)
- Focus blocks (continuous focused periods)
- Notification statistics
"""

from __future__ import annotations

import datetime
import logging
from typing import Optional

from engine.history.store import HistoryStore

logger = logging.getLogger(__name__)


async def compute_daily_stats(
    store: HistoryStore,
    date: Optional[str] = None,
) -> dict:
    """Compute daily statistics from state_log.

    Args:
        store: HistoryStore instance (must be opened).
        date: Date string (YYYY-MM-DD). Defaults to today.

    Returns:
        Dict with daily statistics suitable for save_daily_summary().
    """
    if date is None:
        date = datetime.date.today().isoformat()

    # Parse date boundaries
    dt = datetime.date.fromisoformat(date)
    start_dt = datetime.datetime.combine(dt, datetime.time.min)
    end_dt = datetime.datetime.combine(dt, datetime.time.max)
    start_ts = start_dt.timestamp()
    end_ts = end_dt.timestamp()

    # Fetch state logs for the day
    logs = await store.get_state_log(
        start_time=start_ts,
        end_time=end_ts,
        limit=100000,
    )

    # Sort by timestamp ascending (store returns DESC)
    logs.sort(key=lambda x: x["timestamp"])

    # Compute total time per state
    state_seconds: dict[str, float] = {
        "focused": 0.0,
        "drowsy": 0.0,
        "distracted": 0.0,
        "away": 0.0,
    }

    for i, log in enumerate(logs):
        state = log["integrated_state"]
        if state not in state_seconds:
            continue

        # Estimate duration: time until next log entry, capped at 30s
        if i + 1 < len(logs):
            duration = min(logs[i + 1]["timestamp"] - log["timestamp"], 30.0)
        else:
            duration = 5.0  # assume default interval for last entry

        state_seconds[state] += duration

    # Extract focus blocks (continuous focused periods >= 5 minutes)
    focus_blocks = _extract_focus_blocks(logs, min_block_minutes=5)

    # Fetch notifications for the day
    notifications = await store.get_notifications(
        start_time=start_ts,
        end_time=end_ts,
        limit=1000,
    )

    notification_count = len(notifications)
    notification_accepted = sum(
        1 for n in notifications if n.get("user_action") == "accepted"
    )

    return {
        "date": date,
        "focused_minutes": round(state_seconds["focused"] / 60.0, 1),
        "drowsy_minutes": round(state_seconds["drowsy"] / 60.0, 1),
        "distracted_minutes": round(state_seconds["distracted"] / 60.0, 1),
        "away_minutes": round(state_seconds["away"] / 60.0, 1),
        "idle_minutes": 0.0,  # idle state removed; kept for DB schema compat
        "notification_count": notification_count,
        "notification_accepted": notification_accepted,
        "focus_blocks": focus_blocks,
        "notifications": [
            {
                "type": n["type"],
                "time": datetime.datetime.fromtimestamp(n["timestamp"]).strftime("%H:%M"),
                "action": n.get("user_action"),
            }
            for n in notifications
        ],
    }


def _extract_focus_blocks(
    logs: list[dict],
    min_block_minutes: float = 5.0,
) -> list[dict]:
    """Extract continuous focused blocks from sorted state logs.

    Args:
        logs: State log entries sorted by timestamp ascending.
        min_block_minutes: Minimum block duration to include.

    Returns:
        List of dicts with start, end, duration_min for each block.
    """
    blocks: list[dict] = []
    block_start: Optional[float] = None
    last_focused_ts: float = 0.0

    for log in logs:
        state = log["integrated_state"]
        ts = log["timestamp"]

        if state == "focused":
            if block_start is None:
                block_start = ts
            last_focused_ts = ts
        else:
            if block_start is not None:
                duration_min = (last_focused_ts - block_start) / 60.0
                if duration_min >= min_block_minutes:
                    blocks.append({
                        "start": datetime.datetime.fromtimestamp(block_start).strftime("%H:%M"),
                        "end": datetime.datetime.fromtimestamp(last_focused_ts).strftime("%H:%M"),
                        "duration_min": round(duration_min),
                    })
                block_start = None

    # Handle block that extends to the end
    if block_start is not None:
        duration_min = (last_focused_ts - block_start) / 60.0
        if duration_min >= min_block_minutes:
            blocks.append({
                "start": datetime.datetime.fromtimestamp(block_start).strftime("%H:%M"),
                "end": datetime.datetime.fromtimestamp(last_focused_ts).strftime("%H:%M"),
                "duration_min": round(duration_min),
            })

    return blocks


def build_bucketed_segments(
    logs: list[dict],
    bucket_minutes: int = 5,
    max_entry_duration: float = 30.0,
) -> list[dict]:
    """Group raw state log entries into time-bucketed segments.

    Algorithm (mirrors frontend buildSegments):
      1. Sort by timestamp, compute duration per entry
      2. Assign each entry to a fixed-width time bucket
      3. Majority vote (by total duration) picks the dominant state per bucket
      4. Merge consecutive same-state buckets into segments
      5. Buckets with no data are skipped (produce gaps)

    Args:
        logs: Raw state log entries from get_state_log().
        bucket_minutes: Width of each time bucket in minutes.
        max_entry_duration: Maximum seconds credited to a single entry.

    Returns:
        List of segment dicts with state, start_time, end_time,
        duration_min, and breakdown.
    """
    if not logs:
        return []

    sorted_logs = sorted(logs, key=lambda x: x["timestamp"])
    bucket_size = bucket_minutes * 60

    # Step 1: Assign entries to buckets with duration-weighted states
    # bucket_key -> {state -> total_seconds}
    buckets: dict[float, dict[str, float]] = {}

    for i, log in enumerate(sorted_logs):
        ts = log["timestamp"]
        state = log["integrated_state"]

        # Duration: time until next entry, capped at max_entry_duration.
        # Last entry gets a single poll interval (5s) to match frontend behavior.
        if i + 1 < len(sorted_logs):
            duration = min(
                sorted_logs[i + 1]["timestamp"] - ts,
                max_entry_duration,
            )
        else:
            duration = 5.0

        bucket_key = (ts // bucket_size) * bucket_size

        if bucket_key not in buckets:
            buckets[bucket_key] = {}
        buckets[bucket_key][state] = buckets[bucket_key].get(state, 0.0) + duration

    # Step 2: Pick dominant state per bucket (majority vote by duration)
    bucket_results: list[tuple[float, str, dict[str, float]]] = []
    for bucket_key in sorted(buckets):
        state_durations = buckets[bucket_key]
        dominant_state = max(state_durations, key=lambda s: state_durations[s])
        bucket_results.append((bucket_key, dominant_state, dict(state_durations)))

    # Step 3: Merge consecutive same-state buckets into segments
    segments: list[dict] = []
    for bucket_key, state, breakdown in bucket_results:
        bucket_end = bucket_key + bucket_size

        if segments and segments[-1]["state"] == state:
            last = segments[-1]
            # Only merge if buckets are adjacent (no gap)
            if abs(last["end_time"] - bucket_key) < 1.0:
                last["end_time"] = bucket_end
                last["duration_min"] = (last["end_time"] - last["start_time"]) / 60.0
                # Merge breakdowns
                for s, dur in breakdown.items():
                    last["breakdown"][s] = last["breakdown"].get(s, 0.0) + dur
                continue

        segments.append({
            "state": state,
            "start_time": bucket_key,
            "end_time": bucket_end,
            "duration_min": bucket_size / 60.0,
            "breakdown": dict(breakdown),
        })

    return segments

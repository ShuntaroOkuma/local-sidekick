"""SQLite history store for state logs, notifications, and daily summaries.

Uses aiosqlite for async database access.
Database location: ~/.local-sidekick/history.db
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import aiosqlite

from engine.config import DB_PATH

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS state_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    camera_state TEXT,
    pc_state TEXT,
    integrated_state TEXT NOT NULL,
    confidence REAL,
    source TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    type TEXT NOT NULL,
    message TEXT,
    user_action TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    total_focused_minutes REAL,
    total_drowsy_minutes REAL,
    total_distracted_minutes REAL,
    total_away_minutes REAL,
    total_idle_minutes REAL,
    notification_count INTEGER,
    notification_accepted INTEGER,
    report_text TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_state_log_timestamp ON state_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_notifications_timestamp ON notifications(timestamp);
CREATE INDEX IF NOT EXISTS idx_daily_summary_date ON daily_summary(date);
"""


class HistoryStore:
    """Async SQLite store for state history and notifications."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = Path(db_path) if db_path else DB_PATH
        self._db: Optional[aiosqlite.Connection] = None

    async def open(self) -> None:
        """Open the database and create tables if needed."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        await self._db.executescript(_SCHEMA)
        await self._db.commit()
        logger.info("History store opened at %s", self._db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None
            logger.info("History store closed.")

    async def log_state(
        self,
        timestamp: float,
        camera_state: Optional[str],
        pc_state: Optional[str],
        integrated_state: str,
        confidence: float = 0.0,
        source: str = "rule",
    ) -> None:
        """Record a state observation to the log."""
        if self._db is None:
            return
        await self._db.execute(
            "INSERT INTO state_log (timestamp, camera_state, pc_state, "
            "integrated_state, confidence, source) VALUES (?, ?, ?, ?, ?, ?)",
            (timestamp, camera_state, pc_state, integrated_state, confidence, source),
        )
        await self._db.commit()

    async def log_notification(
        self,
        timestamp: float,
        notification_type: str,
        message: str,
        user_action: Optional[str] = None,
    ) -> None:
        """Record a notification event."""
        if self._db is None:
            return
        await self._db.execute(
            "INSERT INTO notifications (timestamp, type, message, user_action) "
            "VALUES (?, ?, ?, ?)",
            (timestamp, notification_type, message, user_action),
        )
        await self._db.commit()

    async def update_notification_action(
        self,
        notification_id: int,
        user_action: str,
    ) -> None:
        """Update the user_action for a notification."""
        if self._db is None:
            return
        await self._db.execute(
            "UPDATE notifications SET user_action = ? WHERE id = ?",
            (user_action, notification_id),
        )
        await self._db.commit()

    async def get_state_log(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 1000,
    ) -> list[dict]:
        """Retrieve state log entries within a time range."""
        if self._db is None:
            return []

        query = "SELECT id, timestamp, camera_state, pc_state, integrated_state, confidence, source FROM state_log"
        params: list = []
        conditions = []

        if start_time is not None:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        if end_time is not None:
            conditions.append("timestamp <= ?")
            params.append(end_time)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        return [
            {
                "id": row[0],
                "timestamp": row[1],
                "camera_state": row[2],
                "pc_state": row[3],
                "integrated_state": row[4],
                "confidence": row[5],
                "source": row[6],
            }
            for row in rows
        ]

    async def get_notifications(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Retrieve notification entries within a time range."""
        if self._db is None:
            return []

        query = "SELECT id, timestamp, type, message, user_action FROM notifications"
        params: list = []
        conditions = []

        if start_time is not None:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        if end_time is not None:
            conditions.append("timestamp <= ?")
            params.append(end_time)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        return [
            {
                "id": row[0],
                "timestamp": row[1],
                "type": row[2],
                "message": row[3],
                "user_action": row[4],
            }
            for row in rows
        ]

    async def save_daily_summary(self, summary: dict) -> None:
        """Upsert a daily summary record."""
        if self._db is None:
            return
        await self._db.execute(
            "INSERT INTO daily_summary "
            "(date, total_focused_minutes, total_drowsy_minutes, "
            "total_distracted_minutes, total_away_minutes, total_idle_minutes, "
            "notification_count, notification_accepted, report_text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(date) DO UPDATE SET "
            "total_focused_minutes = excluded.total_focused_minutes, "
            "total_drowsy_minutes = excluded.total_drowsy_minutes, "
            "total_distracted_minutes = excluded.total_distracted_minutes, "
            "total_away_minutes = excluded.total_away_minutes, "
            "total_idle_minutes = excluded.total_idle_minutes, "
            "notification_count = excluded.notification_count, "
            "notification_accepted = excluded.notification_accepted, "
            "report_text = excluded.report_text",
            (
                summary["date"],
                summary.get("total_focused_minutes", 0.0),
                summary.get("total_drowsy_minutes", 0.0),
                summary.get("total_distracted_minutes", 0.0),
                summary.get("total_away_minutes", 0.0),
                summary.get("total_idle_minutes", 0.0),
                summary.get("notification_count", 0),
                summary.get("notification_accepted", 0),
                summary.get("report_text"),
            ),
        )
        await self._db.commit()

    async def get_daily_summary(self, date: str) -> Optional[dict]:
        """Get daily summary for a specific date (YYYY-MM-DD)."""
        if self._db is None:
            return None
        async with self._db.execute(
            "SELECT date, total_focused_minutes, total_drowsy_minutes, "
            "total_distracted_minutes, total_away_minutes, total_idle_minutes, "
            "notification_count, notification_accepted, report_text "
            "FROM daily_summary WHERE date = ?",
            (date,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        return {
            "date": row[0],
            "focused_minutes": row[1],
            "drowsy_minutes": row[2],
            "distracted_minutes": row[3],
            "away_minutes": row[4],
            "idle_minutes": row[5],
            "notification_count": row[6],
            "notification_accepted": row[7],
            "report_text": row[8],
        }

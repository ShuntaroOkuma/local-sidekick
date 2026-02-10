"""Statistics upload endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from server.auth import get_current_user
from server.deps import get_firestore
from server.models.schemas import DailyStatistics

router = APIRouter()


@router.post("/")
async def upload_statistics(
    stats: DailyStatistics,
    user: dict = Depends(get_current_user),
):
    """Upload daily statistics to Firestore.

    Stored under ``users/{userId}/daily_stats/{date}``.
    """
    db = get_firestore()
    await db.save_daily_stats(
        user["user_id"],
        stats.date,
        stats.model_dump(),
    )
    return {"status": "ok", "date": stats.date}

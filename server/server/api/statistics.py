"""Statistics upload endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from server.auth import get_current_user
from server.models.schemas import DailyStatistics
from server.services.firestore_client import FirestoreClient

router = APIRouter()

_firestore: FirestoreClient | None = None


def _get_firestore() -> FirestoreClient:
    global _firestore
    if _firestore is None:
        _firestore = FirestoreClient()
    return _firestore


@router.post("/")
async def upload_statistics(
    stats: DailyStatistics,
    user: dict = Depends(get_current_user),
):
    """Upload daily statistics to Firestore.

    Stored under ``users/{userId}/daily_stats/{date}``.
    """
    db = _get_firestore()
    await db.save_daily_stats(
        user["user_id"],
        stats.date,
        stats.model_dump(),
    )
    return {"status": "ok", "date": stats.date}

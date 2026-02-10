"""Settings sync CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from server.auth import get_current_user
from server.models.schemas import SettingsResponse, SettingsUpdate
from server.services.firestore_client import FirestoreClient

router = APIRouter()

DEFAULT_SETTINGS: dict = {
    "working_hours_start": "09:00",
    "working_hours_end": "19:00",
    "max_notifications_per_day": 6,
    "camera_enabled": True,
    "sync_enabled": True,
}

_firestore: FirestoreClient | None = None


def _get_firestore() -> FirestoreClient:
    global _firestore
    if _firestore is None:
        _firestore = FirestoreClient()
    return _firestore


@router.get("/", response_model=SettingsResponse)
async def get_settings(user: dict = Depends(get_current_user)):
    """Retrieve user settings. Returns defaults if none are stored."""
    db = _get_firestore()
    stored = await db.get_settings(user["user_id"])
    if stored is None:
        return SettingsResponse(**DEFAULT_SETTINGS)
    merged = {**DEFAULT_SETTINGS, **stored}
    return SettingsResponse(**merged)


@router.put("/", response_model=SettingsResponse)
async def update_settings(
    settings: SettingsUpdate,
    user: dict = Depends(get_current_user),
):
    """Update user settings (partial update via merge)."""
    db = _get_firestore()
    # Only include fields that were explicitly set
    update_data = settings.model_dump(exclude_none=True)
    if update_data:
        await db.update_settings(user["user_id"], update_data)
    # Return the merged result
    stored = await db.get_settings(user["user_id"])
    merged = {**DEFAULT_SETTINGS, **(stored or {})}
    return SettingsResponse(**merged)

"""Firestore client with in-memory fallback for local development."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class InMemoryStore:
    """In-memory fallback when Firestore is unavailable."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def _key(self, *parts: str) -> str:
        return "/".join(parts)

    async def get_document(self, *path: str) -> dict | None:
        return self._data.get(self._key(*path))

    async def set_document(self, *path: str, data: dict, merge: bool = False) -> None:
        key = self._key(*path)
        if merge and key in self._data:
            self._data[key].update(data)
        else:
            self._data[key] = dict(data)

    async def find_user_by_email(self, email: str) -> tuple[str | None, dict | None]:
        """Search for a user document by email field."""
        for key, doc in self._data.items():
            if key.startswith("users/") and key.count("/") == 1:
                if doc.get("email") == email:
                    user_id = key.split("/")[1]
                    return user_id, doc
        return None, None


class FirestoreClient:
    """Firestore wrapper with automatic fallback to in-memory store."""

    def __init__(self) -> None:
        self._firestore_db = None
        self._memory = InMemoryStore()
        self._use_memory = False
        self._init_firestore()

    def _init_firestore(self) -> None:
        """Attempt to initialise the Firestore async client."""
        if os.environ.get("USE_MEMORY_STORE", "").lower() in ("1", "true", "yes"):
            logger.info("USE_MEMORY_STORE is set. Using in-memory store.")
            self._use_memory = True
            return
        try:
            import google.auth  # type: ignore[import-untyped]

            credentials, project = google.auth.default()
            if project is None:
                raise RuntimeError("No GCP project configured")
            from google.cloud import firestore  # type: ignore[import-untyped]

            self._firestore_db = firestore.AsyncClient(
                project=project, credentials=credentials
            )
            logger.info("Firestore client initialised (project=%s)", project)
        except Exception as exc:
            logger.warning(
                "Firestore unavailable (%s). Using in-memory store.", exc
            )
            self._use_memory = True

    # ------------------------------------------------------------------
    # User helpers
    # ------------------------------------------------------------------

    async def get_user(self, user_id: str) -> dict | None:
        if self._use_memory:
            return await self._memory.get_document("users", user_id)
        doc = await self._firestore_db.collection("users").document(user_id).get()
        return doc.to_dict() if doc.exists else None

    async def create_user(self, user_id: str, data: dict) -> None:
        if self._use_memory:
            await self._memory.set_document("users", user_id, data=data)
            return
        await self._firestore_db.collection("users").document(user_id).set(data)

    async def find_user_by_email(self, email: str) -> tuple[str | None, dict | None]:
        """Return (user_id, user_doc) or (None, None)."""
        if self._use_memory:
            return await self._memory.find_user_by_email(email)
        query = (
            self._firestore_db.collection("users")
            .where("email", "==", email)
            .limit(1)
        )
        docs = []
        async for doc in query.stream():
            docs.append(doc)
        if docs:
            return docs[0].id, docs[0].to_dict()
        return None, None

    # ------------------------------------------------------------------
    # Settings helpers
    # ------------------------------------------------------------------

    async def get_settings(self, user_id: str) -> dict | None:
        if self._use_memory:
            return await self._memory.get_document("users", user_id, "settings", "current")
        doc = (
            await self._firestore_db.collection("users")
            .document(user_id)
            .collection("settings")
            .document("current")
            .get()
        )
        return doc.to_dict() if doc.exists else None

    async def update_settings(self, user_id: str, settings: dict) -> None:
        if self._use_memory:
            await self._memory.set_document(
                "users", user_id, "settings", "current", data=settings, merge=True
            )
            return
        await (
            self._firestore_db.collection("users")
            .document(user_id)
            .collection("settings")
            .document("current")
            .set(settings, merge=True)
        )

    # ------------------------------------------------------------------
    # Daily stats helpers
    # ------------------------------------------------------------------

    async def save_daily_stats(self, user_id: str, date: str, stats: dict) -> None:
        if self._use_memory:
            await self._memory.set_document(
                "users", user_id, "daily_stats", date, data=stats
            )
            return
        await (
            self._firestore_db.collection("users")
            .document(user_id)
            .collection("daily_stats")
            .document(date)
            .set(stats)
        )

    async def get_daily_stats(self, user_id: str, date: str) -> dict | None:
        if self._use_memory:
            return await self._memory.get_document(
                "users", user_id, "daily_stats", date
            )
        doc = (
            await self._firestore_db.collection("users")
            .document(user_id)
            .collection("daily_stats")
            .document(date)
            .get()
        )
        return doc.to_dict() if doc.exists else None

    # ------------------------------------------------------------------
    # Report helpers
    # ------------------------------------------------------------------

    async def save_report(self, user_id: str, date: str, report: dict) -> None:
        if self._use_memory:
            await self._memory.set_document(
                "users", user_id, "reports", date, data=report
            )
            return
        await (
            self._firestore_db.collection("users")
            .document(user_id)
            .collection("reports")
            .document(date)
            .set(report)
        )

    async def get_report(self, user_id: str, date: str) -> dict | None:
        if self._use_memory:
            return await self._memory.get_document("users", user_id, "reports", date)
        doc = (
            await self._firestore_db.collection("users")
            .document(user_id)
            .collection("reports")
            .document(date)
            .get()
        )
        return doc.to_dict() if doc.exists else None

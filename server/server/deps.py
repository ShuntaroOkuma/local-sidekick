"""Shared dependencies for FastAPI dependency injection."""

from __future__ import annotations

from server.services.firestore_client import FirestoreClient

_firestore: FirestoreClient | None = None


def get_firestore() -> FirestoreClient:
    """Return the shared FirestoreClient singleton."""
    global _firestore
    if _firestore is None:
        _firestore = FirestoreClient()
    return _firestore

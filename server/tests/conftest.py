"""Shared test fixtures."""

from __future__ import annotations

import os

import pytest

# Force in-memory store for all tests
os.environ["USE_MEMORY_STORE"] = "1"
os.environ["JWT_SECRET"] = "test-secret-for-testing"


@pytest.fixture()
def memory_store():
    """Return a fresh InMemoryStore instance."""
    from server.services.firestore_client import InMemoryStore

    return InMemoryStore()


@pytest.fixture()
def firestore_client():
    """Return a fresh FirestoreClient backed by in-memory store."""
    from server.services.firestore_client import FirestoreClient

    client = FirestoreClient()
    # Reset the in-memory data for test isolation
    client._memory._data.clear()
    return client

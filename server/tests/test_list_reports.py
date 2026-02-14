"""Tests for report listing: InMemoryStore.list_documents,
FirestoreClient.list_report_dates, and GET /api/reports/ endpoint."""

from __future__ import annotations

import os

os.environ.setdefault("USE_MEMORY_STORE", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-for-testing")

import pytest
from httpx import ASGITransport, AsyncClient

from server.auth import _create_token
from server.main import app

# ---------------------------------------------------------------------------
# InMemoryStore.list_documents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_documents_empty(memory_store):
    result = await memory_store.list_documents("users", "u1", "reports")
    assert result == []


@pytest.mark.asyncio
async def test_list_documents_single(memory_store):
    await memory_store.set_document(
        "users", "u1", "reports", "2026-02-15", data={"summary": "ok"}
    )
    result = await memory_store.list_documents("users", "u1", "reports")
    assert result == ["2026-02-15"]


@pytest.mark.asyncio
async def test_list_documents_multiple(memory_store):
    await memory_store.set_document(
        "users", "u1", "reports", "2026-02-13", data={"summary": "a"}
    )
    await memory_store.set_document(
        "users", "u1", "reports", "2026-02-14", data={"summary": "b"}
    )
    await memory_store.set_document(
        "users", "u1", "reports", "2026-02-15", data={"summary": "c"}
    )
    result = await memory_store.list_documents("users", "u1", "reports")
    assert len(result) == 3
    assert set(result) == {"2026-02-13", "2026-02-14", "2026-02-15"}


@pytest.mark.asyncio
async def test_list_documents_ignores_other_collections(memory_store):
    await memory_store.set_document(
        "users", "u1", "reports", "2026-02-15", data={"summary": "ok"}
    )
    await memory_store.set_document(
        "users", "u1", "daily_stats", "2026-02-15", data={"focused_minutes": 60}
    )
    result = await memory_store.list_documents("users", "u1", "reports")
    assert result == ["2026-02-15"]


# ---------------------------------------------------------------------------
# FirestoreClient.list_report_dates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_report_dates_empty(firestore_client):
    dates = await firestore_client.list_report_dates("u1")
    assert dates == []


@pytest.mark.asyncio
async def test_list_report_dates_sorted_descending(firestore_client):
    await firestore_client.save_report("u1", "2026-02-10", {"summary": "a", "highlights": [], "concerns": [], "tomorrow_tip": ""})
    await firestore_client.save_report("u1", "2026-02-15", {"summary": "c", "highlights": [], "concerns": [], "tomorrow_tip": ""})
    await firestore_client.save_report("u1", "2026-02-12", {"summary": "b", "highlights": [], "concerns": [], "tomorrow_tip": ""})

    dates = await firestore_client.list_report_dates("u1")
    assert dates == ["2026-02-15", "2026-02-12", "2026-02-10"]


@pytest.mark.asyncio
async def test_list_report_dates_per_user(firestore_client):
    await firestore_client.save_report("u1", "2026-02-15", {"summary": "x", "highlights": [], "concerns": [], "tomorrow_tip": ""})
    await firestore_client.save_report("u2", "2026-02-14", {"summary": "y", "highlights": [], "concerns": [], "tomorrow_tip": ""})

    dates_u1 = await firestore_client.list_report_dates("u1")
    dates_u2 = await firestore_client.list_report_dates("u2")
    assert dates_u1 == ["2026-02-15"]
    assert dates_u2 == ["2026-02-14"]


# ---------------------------------------------------------------------------
# GET /api/reports/ endpoint
# ---------------------------------------------------------------------------

_TEST_USER_ID = "test-user-id-123"
_TEST_EMAIL = "test@example.com"


def _auth_header() -> dict[str, str]:
    token = _create_token(_TEST_USER_ID, _TEST_EMAIL)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _reset_firestore_singleton():
    """Reset the Firestore singleton before each test."""
    from server import deps

    original = deps._firestore
    deps._firestore = None
    yield
    deps._firestore = original


@pytest.mark.asyncio
async def test_list_reports_endpoint_empty():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/reports/", headers=_auth_header())
    assert resp.status_code == 200
    assert resp.json() == {"dates": []}


@pytest.mark.asyncio
async def test_list_reports_endpoint_with_data():
    from server.deps import get_firestore

    db = get_firestore()
    await db.save_report(_TEST_USER_ID, "2026-02-10", {"summary": "a", "highlights": [], "concerns": [], "tomorrow_tip": ""})
    await db.save_report(_TEST_USER_ID, "2026-02-15", {"summary": "b", "highlights": [], "concerns": [], "tomorrow_tip": ""})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/reports/", headers=_auth_header())
    assert resp.status_code == 200
    data = resp.json()
    assert data["dates"] == ["2026-02-15", "2026-02-10"]


@pytest.mark.asyncio
async def test_list_reports_endpoint_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/reports/")
    assert resp.status_code in (401, 403)

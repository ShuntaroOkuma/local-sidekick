"""Daily report generation and retrieval endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from server.auth import get_current_user
from server.models.schemas import DailyReport, ReportRequest
from server.services.firestore_client import FirestoreClient
from server.services.vertex_ai import VertexAIService

router = APIRouter()

_firestore: FirestoreClient | None = None
_vertex: VertexAIService | None = None


def _get_firestore() -> FirestoreClient:
    global _firestore
    if _firestore is None:
        _firestore = FirestoreClient()
    return _firestore


def _get_vertex() -> VertexAIService:
    global _vertex
    if _vertex is None:
        _vertex = VertexAIService()
    return _vertex


@router.post("/generate", response_model=DailyReport)
async def generate_report(
    request: ReportRequest,
    user: dict = Depends(get_current_user),
):
    """Generate a daily report using Vertex AI (Gemini).

    Steps:
    1. Build stats dict from the request body
    2. Send to Vertex AI for natural-language report generation
    3. Save report to Firestore
    4. Return the generated report
    """
    db = _get_firestore()
    vertex = _get_vertex()

    # Prepare stats payload for the AI prompt
    stats_dict = request.model_dump()

    # Convert nested Pydantic models to plain dicts for the prompt
    stats_dict["focus_blocks"] = [
        fb if isinstance(fb, dict) else fb
        for fb in stats_dict.get("focus_blocks", [])
    ]

    # Generate the report via Vertex AI (or dummy fallback)
    report_data = await vertex.generate_daily_report(stats_dict)

    # Save to Firestore
    await db.save_report(user["user_id"], request.date, report_data)

    return DailyReport(**report_data)


@router.get("/{date}", response_model=DailyReport)
async def get_report(
    date: str,
    user: dict = Depends(get_current_user),
):
    """Retrieve a previously generated report for the given date."""
    db = _get_firestore()

    report = await db.get_report(user["user_id"], date)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No report found for date: {date}",
        )

    return DailyReport(**report)

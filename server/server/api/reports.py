"""Daily report generation and retrieval endpoints."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from server.auth import get_current_user
from server.deps import get_firestore
from server.models.schemas import DailyReport, ReportRequest
from server.services.vertex_ai import VertexAIService

router = APIRouter()

_vertex: VertexAIService | None = None


def _get_vertex() -> VertexAIService:
    global _vertex
    if _vertex is None:
        _vertex = VertexAIService()
    return _vertex


@router.get("/")
async def list_reports(
    user: dict = Depends(get_current_user),
):
    """List available report dates."""
    db = get_firestore()
    dates = await db.list_report_dates(user["user_id"])
    return {"dates": dates}


@router.post("/generate", response_model=DailyReport)
async def generate_report(
    request: ReportRequest,
    user: dict = Depends(get_current_user),
):
    """Generate a daily report using Vertex AI (Gemini)."""
    db = get_firestore()
    vertex = _get_vertex()

    stats_dict = request.model_dump()
    stats_dict["focus_blocks"] = [
        fb if isinstance(fb, dict) else fb
        for fb in stats_dict.get("focus_blocks", [])
    ]

    report_data = await vertex.generate_daily_report(stats_dict)
    await db.save_report(user["user_id"], request.date, report_data)

    return DailyReport(**report_data)


@router.get("/{date}", response_model=DailyReport)
async def get_report(
    date: str,
    user: dict = Depends(get_current_user),
):
    """Retrieve a previously generated report for the given date."""
    # Validate date format
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD",
        )

    db = get_firestore()
    report = await db.get_report(user["user_id"], date)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No report found for date: {date}",
        )

    return DailyReport(**report)

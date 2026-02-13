"""HTTP client for Cloud Run API (auth + report generation)."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


async def cloud_health_check(base_url: str) -> bool:
    """Check if the Cloud Run URL is reachable by hitting /api/health."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{base_url}/api/health", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("status") == "ok"
    except httpx.HTTPError as exc:
        logger.warning("cloud_health_check failed: %s", exc)
        return False


async def cloud_login(base_url: str, email: str, password: str) -> dict | None:
    """Login to Cloud Run, return token dict or None on error."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url}/api/auth/login",
                json={"email": email, "password": password},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        logger.warning("cloud_login failed: %s", exc)
        return None


async def cloud_register(base_url: str, email: str, password: str) -> dict | None:
    """Register on Cloud Run, return token dict or None on error."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url}/api/auth/register",
                json={"email": email, "password": password},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        logger.warning("cloud_register failed: %s", exc)
        return None


async def cloud_generate_report(
    base_url: str, token: str, stats: dict
) -> dict | None:
    """Proxy report generation to Cloud Run, return DailyReport dict or None on error."""
    try:
        # Build a payload matching the server's ReportRequest schema
        payload = {
            "date": stats.get("date", ""),
            "focused_minutes": stats.get("focused_minutes", 0),
            "drowsy_minutes": stats.get("drowsy_minutes", 0),
            "distracted_minutes": stats.get("distracted_minutes", 0),
            "away_minutes": stats.get("away_minutes", 0),
            "idle_minutes": stats.get("idle_minutes", 0),
            "notification_count": stats.get("notification_count", 0),
            "focus_blocks": stats.get("focus_blocks", []),
            "notifications": [
                {
                    "type": n.get("type", ""),
                    "time": n.get("time", ""),
                    "action": n.get("action") or "none",
                }
                for n in stats.get("notifications", [])
            ],
            "top_apps": stats.get("top_apps", []),
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url}/api/reports/generate",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        logger.warning("cloud_generate_report failed: %s", exc)
        return None

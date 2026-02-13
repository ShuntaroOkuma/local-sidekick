"""HTTP client for Cloud Run API (auth + report generation)."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


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
    except (httpx.HTTPError, Exception) as exc:
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
    except (httpx.HTTPError, Exception) as exc:
        logger.warning("cloud_register failed: %s", exc)
        return None


async def cloud_generate_report(
    base_url: str, token: str, stats: dict
) -> dict | None:
    """Proxy report generation to Cloud Run, return DailyReport dict or None on error."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url}/api/reports/generate",
                json=stats,
                headers={"Authorization": f"Bearer {token}"},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPError, Exception) as exc:
        logger.warning("cloud_generate_report failed: %s", exc)
        return None

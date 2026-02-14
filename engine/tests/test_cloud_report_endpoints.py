"""Tests for cloud report proxy functions and GET /reports endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from engine.api.cloud_client import cloud_get_report, cloud_list_reports


# --- cloud_get_report tests ---


class TestCloudGetReport:
    @pytest.mark.asyncio
    async def test_success_returns_dict(self):
        """Successful response returns parsed JSON dict."""
        mock_response = httpx.Response(
            200,
            json={"date": "2026-02-14", "summary": "Good day"},
            request=httpx.Request("GET", "http://test/api/reports/2026-02-14"),
        )
        with patch("engine.api.cloud_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await cloud_get_report("http://test", "tok", "2026-02-14")

        assert result == {"date": "2026-02-14", "summary": "Good day"}
        mock_client.get.assert_called_once_with(
            "http://test/api/reports/2026-02-14",
            headers={"Authorization": "Bearer tok"},
            timeout=10,
        )

    @pytest.mark.asyncio
    async def test_404_returns_none(self):
        """404 response returns None."""
        mock_response = httpx.Response(
            404,
            request=httpx.Request("GET", "http://test/api/reports/2020-01-01"),
        )
        with patch("engine.api.cloud_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            # raise_for_status will raise on 404
            mock_response.raise_for_status = lambda: (_ for _ in ()).throw(
                httpx.HTTPStatusError(
                    "404", request=mock_response.request, response=mock_response
                )
            )

            result = await cloud_get_report("http://test", "tok", "2020-01-01")

        assert result is None

    @pytest.mark.asyncio
    async def test_connection_error_returns_none(self):
        """Connection error returns None."""
        with patch("engine.api.cloud_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await cloud_get_report("http://test", "tok", "2026-02-14")

        assert result is None


# --- cloud_list_reports tests ---


class TestCloudListReports:
    @pytest.mark.asyncio
    async def test_success_returns_list(self):
        """Successful response returns list of date strings."""
        mock_response = httpx.Response(
            200,
            json={"dates": ["2026-02-14", "2026-02-13"]},
            request=httpx.Request("GET", "http://test/api/reports"),
        )
        with patch("engine.api.cloud_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await cloud_list_reports("http://test", "tok")

        assert result == ["2026-02-14", "2026-02-13"]
        mock_client.get.assert_called_once_with(
            "http://test/api/reports",
            headers={"Authorization": "Bearer tok"},
            timeout=10,
        )

    @pytest.mark.asyncio
    async def test_error_returns_none(self):
        """HTTP error returns None."""
        with patch("engine.api.cloud_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await cloud_list_reports("http://test", "tok")

        assert result is None

    @pytest.mark.asyncio
    async def test_missing_dates_key_returns_empty_list(self):
        """Response without 'dates' key returns empty list."""
        mock_response = httpx.Response(
            200,
            json={"something_else": True},
            request=httpx.Request("GET", "http://test/api/reports"),
        )
        with patch("engine.api.cloud_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await cloud_list_reports("http://test", "tok")

        assert result == []


# --- Route endpoint tests ---


class TestListReportsEndpoint:
    @pytest.mark.asyncio
    async def test_sync_disabled_returns_empty(self):
        """When sync is disabled, returns empty dates list."""
        from engine.api.routes import list_reports

        with patch("engine.api.routes.load_config") as mock_config:
            mock_config.return_value.sync_enabled = False
            mock_config.return_value.cloud_run_url = ""
            mock_config.return_value.cloud_auth_token = ""

            result = await list_reports()

        assert result == {"dates": []}

    @pytest.mark.asyncio
    async def test_sync_enabled_returns_dates(self):
        """When sync is enabled, proxies to cloud and returns dates."""
        from engine.api.routes import list_reports

        with (
            patch("engine.api.routes.load_config") as mock_config,
            patch("engine.api.routes.cloud_list_reports", new_callable=AsyncMock) as mock_list,
        ):
            mock_config.return_value.sync_enabled = True
            mock_config.return_value.cloud_run_url = "http://cloud"
            mock_config.return_value.cloud_auth_token = "tok"
            mock_list.return_value = ["2026-02-14", "2026-02-13"]

            result = await list_reports()

        assert result == {"dates": ["2026-02-14", "2026-02-13"]}
        mock_list.assert_called_once_with("http://cloud", "tok")

    @pytest.mark.asyncio
    async def test_cloud_failure_returns_empty(self):
        """When cloud call fails, returns empty dates list."""
        from engine.api.routes import list_reports

        with (
            patch("engine.api.routes.load_config") as mock_config,
            patch("engine.api.routes.cloud_list_reports", new_callable=AsyncMock) as mock_list,
        ):
            mock_config.return_value.sync_enabled = True
            mock_config.return_value.cloud_run_url = "http://cloud"
            mock_config.return_value.cloud_auth_token = "tok"
            mock_list.return_value = None

            result = await list_reports()

        assert result == {"dates": []}


class TestGetReportEndpoint:
    @pytest.mark.asyncio
    async def test_sync_disabled_raises_503(self):
        """When sync is disabled, raises 503."""
        from fastapi import HTTPException

        from engine.api.routes import get_report

        with patch("engine.api.routes.load_config") as mock_config:
            mock_config.return_value.sync_enabled = False
            mock_config.return_value.cloud_run_url = ""
            mock_config.return_value.cloud_auth_token = ""

            with pytest.raises(HTTPException) as exc_info:
                await get_report("2026-02-14")

            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_report_found(self):
        """When report exists, returns it."""
        from engine.api.routes import get_report

        with (
            patch("engine.api.routes.load_config") as mock_config,
            patch("engine.api.routes.cloud_get_report", new_callable=AsyncMock) as mock_get,
        ):
            mock_config.return_value.sync_enabled = True
            mock_config.return_value.cloud_run_url = "http://cloud"
            mock_config.return_value.cloud_auth_token = "tok"
            mock_get.return_value = {"date": "2026-02-14", "summary": "Great"}

            result = await get_report("2026-02-14")

        assert result == {"date": "2026-02-14", "summary": "Great"}
        mock_get.assert_called_once_with("http://cloud", "tok", "2026-02-14")

    @pytest.mark.asyncio
    async def test_report_not_found_raises_404(self):
        """When report is not found, raises 404."""
        from fastapi import HTTPException

        from engine.api.routes import get_report

        with (
            patch("engine.api.routes.load_config") as mock_config,
            patch("engine.api.routes.cloud_get_report", new_callable=AsyncMock) as mock_get,
        ):
            mock_config.return_value.sync_enabled = True
            mock_config.return_value.cloud_run_url = "http://cloud"
            mock_config.return_value.cloud_auth_token = "tok"
            mock_get.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await get_report("2020-01-01")

            assert exc_info.value.status_code == 404

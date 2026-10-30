"""
Integration and End-to-End API tests for FastAPI backend using pytest + httpx.
Tests cover:
- Health check and in-memory data store verification.
- Latest forecast endpoint with settlement period intervals and outturn actuals.
- Forecast vintages revision evolution endpoint.
- Accuracy summary, metrics, and error distribution.
- Breakdowns by day, hour, horizon, and wind level.
- Out-of-bounds date validation (enforcing strictly January 2026).
- Invalid cutoff times and query parameter error handling.
- OpenAPI specification completeness.
"""

import pytest
import httpx
from backend.app.main import app
from backend.app.data_store import data_store
from backend.app.config import settings


@pytest.fixture(scope="session", autouse=True)
def load_test_data():
    """Ensure data is loaded into memory before running API tests."""
    data_store.load(settings.DATA_DIR)


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test GET /api/health."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["dataLoaded"] is True
        assert data["fuelhhRecords"] > 0
        assert data["windforRecords"] > 0
        assert "January 2026" in data["scope"]


@pytest.mark.asyncio
async def test_get_latest_forecast_valid():
    """Test GET /api/forecast/latest for a valid delivery day in Jan 2026."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/forecast/latest", params={"delivery_date": "2026-01-05", "cutoff": "09:00"})
        assert resp.status_code == 200
        data = resp.json()

        assert data["deliveryDate"] == "2026-01-05"
        assert data["cutoffTime"] == "09:00"
        assert "cutoffUtc" in data

        intervals = data["intervals"]
        assert len(intervals) == 48

        # Verify interval fields
        first_sp = intervals[0]
        assert first_sp["settlementPeriod"] == 1
        assert "startTime" in first_sp
        assert first_sp["forecast"] is not None
        assert first_sp["actual"] is not None
        assert first_sp["error"] is not None
        assert first_sp["publishTime"] is not None

        # Verify summary metrics
        sm = data["summaryMetrics"]
        assert sm is not None
        assert sm["recordCount"] == 48
        assert sm["mae"] is not None and sm["mae"] > 0
        assert sm["rmse"] is not None and sm["rmse"] > 0


@pytest.mark.asyncio
async def test_get_latest_forecast_out_of_bounds_date():
    """Test that requesting dates outside January 2026 returns 400 Bad Request."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Before Jan 2026
        resp = await client.get("/api/forecast/latest", params={"delivery_date": "2025-12-31"})
        assert resp.status_code == 400
        assert "strictly January 2026" in resp.json()["detail"]

        # After Jan 2026
        resp = await client.get("/api/forecast/latest", params={"delivery_date": "2026-02-01"})
        assert resp.status_code == 400
        assert "strictly January 2026" in resp.json()["detail"]

        # Malformed date
        resp = await client.get("/api/forecast/latest", params={"delivery_date": "invalid-date"})
        assert resp.status_code == 400
        assert "Expected 'YYYY-MM-DD'" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_latest_forecast_invalid_cutoff():
    """Test invalid cutoff times return 400."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/forecast/latest", params={"delivery_date": "2026-01-05", "cutoff": "25:00"})
        assert resp.status_code == 400
        assert "Hours must be 00-23" in resp.json()["detail"]

        resp = await client.get("/api/forecast/latest", params={"delivery_date": "2026-01-05", "cutoff": "noon"})
        assert resp.status_code == 400
        assert "Expected format 'HH:MM'" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_forecast_vintages_valid():
    """Test GET /api/forecast/vintages returns historical publication runs."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/forecast/vintages", params={"target_date": "2026-01-05"})
        assert resp.status_code == 200
        data = resp.json()

        assert data["targetDate"] == "2026-01-05"
        assert data["vintagesCount"] > 0
        assert len(data["actualOutturns"]) == 48

        first_vintage = data["vintages"][0]
        assert "publishTime" in first_vintage
        assert "leadHoursToDayStart" in first_vintage
        assert len(first_vintage["points"]) > 0


@pytest.mark.asyncio
async def test_get_forecast_vintages_out_of_bounds():
    """Test out of bounds target_date in vintages."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/forecast/vintages", params={"target_date": "2026-02-10"})
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_accuracy_summary_valid():
    """Test GET /api/accuracy/summary for January date range."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/accuracy/summary",
            params={"start": "2026-01-01", "end": "2026-01-05", "cutoff": "09:00"}
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["startDate"] == "2026-01-01"
        assert data["endDate"] == "2026-01-05"
        assert data["cutoffTime"] == "09:00"

        # 5 days * 48 = 240 periods
        m = data["metrics"]
        assert m["recordCount"] == 240
        assert m["mae"] is not None and m["mae"] > 0
        assert m["rmse"] is not None
        assert m["meanBias"] is not None
        assert m["mape"] is not None

        # Error distribution
        ed = data["errorDistribution"]
        assert "P50" in ed["quantiles"]
        assert "P90" in ed["quantiles"]
        assert ed["p90ShortfallMW"] is not None
        assert len(ed["histogram"]) > 0


@pytest.mark.asyncio
async def test_get_accuracy_summary_invalid_range():
    """Test reversed date range (start > end) returns 400."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/accuracy/summary",
            params={"start": "2026-01-10", "end": "2026-01-05"}
        )
        assert resp.status_code == 400
        assert "cannot be after" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_accuracy_breakdown_all_dimensions():
    """Test GET /api/accuracy/breakdown for day, hour, horizon, level."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for dim in ["day", "hour", "horizon", "level"]:
            resp = await client.get(
                "/api/accuracy/breakdown",
                params={"by": dim, "start": "2026-01-01", "end": "2026-01-03", "cutoff": "09:00"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["breakdownBy"] == dim
            assert len(data["items"]) > 0

        # Invalid dimension returns 422 Unprocessable Entity
        resp_invalid = await client.get("/api/accuracy/breakdown", params={"by": "unsupported_dim"})
        assert resp_invalid.status_code == 422


@pytest.mark.asyncio
async def test_get_error_distribution_endpoint():
    """Test GET /api/accuracy/error-distribution."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/accuracy/error-distribution",
            params={"start": "2026-01-01", "end": "2026-01-07", "cutoff": "09:00"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "quantiles" in data
        assert "P90" in data["quantiles"]
        assert data["p90ShortfallMW"] is not None
        assert data["overforecastProbabilityPct"] is not None
        assert data["underforecastProbabilityPct"] is not None
        assert len(data["histogram"]) > 0


@pytest.mark.asyncio
async def test_openapi_documentation_accessible():
    """Verify OpenAPI spec is generated and contains all required paths."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()

        paths = spec["paths"]
        expected_endpoints = [
            "/api/health",
            "/api/forecast/latest",
            "/api/forecast/vintages",
            "/api/accuracy/summary",
            "/api/accuracy/breakdown",
            "/api/accuracy/error-distribution",
        ]
        for ep in expected_endpoints:
            assert ep in paths, f"Expected endpoint {ep} not found in OpenAPI spec!"


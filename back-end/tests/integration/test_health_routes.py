import pytest
from unittest.mock import AsyncMock, patch


async def test_liveness_always_200(client):
    resp = await client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_readiness_with_healthy_db(client, mock_db):
    mock_db.command = AsyncMock(return_value={"ok": 1})
    with patch(
        "app.routes.v1.health_routes.EvidenceRepository.check_connectivity",
        new=AsyncMock(return_value=True),
    ):
        resp = await client.get("/api/v1/health/ready")
    assert resp.status_code == 200


async def test_readiness_503_when_db_down(client):
    with patch(
        "app.routes.v1.health_routes.get_db", return_value=None
    ):
        resp = await client.get("/api/v1/health/ready")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"

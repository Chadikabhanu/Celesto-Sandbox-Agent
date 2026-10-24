from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture
def client():
    # Use TestClient with raise_server_exceptions=False so HTTPExceptions return status codes
    return TestClient(app, raise_server_exceptions=False)


def test_api_health_endpoint_healthy(client):
    """GET /health returns 200 OK and {'status': 'ok'} when DB is healthy."""
    with patch("src.main.check_db_health", new_callable=AsyncMock) as mock_health:
        mock_health.return_value = True
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_api_health_endpoint_unhealthy(client):
    """GET /health returns 503 Service Unavailable when DB is unreachable."""
    with patch("src.main.check_db_health", new_callable=AsyncMock) as mock_health:
        mock_health.return_value = False
        resp = client.get("/health")
        assert resp.status_code == 503
        assert resp.json()["detail"]["status"] == "unhealthy"


def test_api_get_runs_list(client):
    """GET /api/runs returns JSON array of run records including seeded sbx-seeddemo1."""
    mock_runs = [
        {
            "id": 1,
            "sandbox_name": "sbx-seeddemo1",
            "state": "deleted",
            "execution_target": "celesto_sandbox",
            "task_id": "task-seed-01",
            "metadata": {"seeded": True},
            "created_at": "2026-10-23T08:00:00Z",
            "updated_at": "2026-10-23T08:00:00Z",
        }
    ]
    with patch("src.main.fetch_all_runs", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_runs
        resp = client.get("/api/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["sandbox_name"] == "sbx-seeddemo1"
        assert data[0]["state"] == "deleted"
        assert data[0]["execution_target"] == "celesto_sandbox"


def test_api_create_run_valid(client):
    """POST /api/runs creates new run with valid payload and returns 201."""
    inserted = {
        "id": 42,
        "sandbox_name": "sbx-valid123456",
        "state": "pending",
        "execution_target": "celesto_sandbox",
        "task_id": "task-01",
        "metadata": {"source": "unit_test"},
        "created_at": "2026-10-24T10:00:00Z",
        "updated_at": "2026-10-24T10:00:00Z",
    }
    with patch("src.main.insert_run", new_callable=AsyncMock) as mock_insert:
        mock_insert.return_value = inserted
        payload = {
            "sandbox_name": "sbx-valid123456",
            "state": "pending",
            "execution_target": "celesto_sandbox",
            "task_id": "task-01",
            "metadata": {"source": "unit_test"},
        }
        resp = client.post("/api/runs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == 42
        assert data["sandbox_name"] == "sbx-valid123456"
        assert data["state"] == "pending"


@pytest.mark.parametrize(
    "invalid_name",
    [
        "invalid",
        "sbx-123",
        "sbx-UPPERCASE123",
        "sbx-special_char!",
        "host-machine",
        "",
    ],
)
def test_api_reject_invalid_sandbox_name(client, invalid_name):
    """POST /api/runs rejects invalid sandbox_name format with 400 Bad Request."""
    payload = {
        "sandbox_name": invalid_name,
        "state": "pending",
        "execution_target": "celesto_sandbox",
    }
    resp = client.post("/api/runs", json=payload)
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "invalid_state",
    [
        "invalid_state",
        "unknown",
        "active",
        "running_now",
    ],
)
def test_api_reject_invalid_state(client, invalid_state):
    """POST /api/runs rejects invalid lifecycle states with 400 Bad Request."""
    payload = {
        "sandbox_name": "sbx-validname123",
        "state": invalid_state,
        "execution_target": "celesto_sandbox",
    }
    resp = client.post("/api/runs", json=payload)
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "invalid_target",
    [
        "host_subprocess",
        "docker_host",
        "untrusted_vm",
        "bare_metal",
    ],
)
def test_api_reject_invalid_execution_target(client, invalid_target):
    """POST /api/runs rejects unauthorized execution targets with 400 Bad Request."""
    payload = {
        "sandbox_name": "sbx-validname123",
        "state": "pending",
        "execution_target": invalid_target,
    }
    resp = client.post("/api/runs", json=payload)
    assert resp.status_code == 400


def test_api_reject_missing_required_fields(client):
    """POST /api/runs rejects payloads missing required sandbox_name with 400 Bad Request."""
    resp = client.post("/api/runs", json={"state": "pending"})
    assert resp.status_code == 400

    resp2 = client.post("/api/runs", json={})
    assert resp2.status_code == 400


def test_api_reject_duplicate_sandbox_name(client):
    """POST /api/runs with duplicate sandbox_name returns 400 Bad Request."""
    with patch("src.main.insert_run", new_callable=AsyncMock) as mock_insert:
        mock_insert.side_effect = ValueError("Sandbox 'sbx-seeddemo1' already exists.")
        payload = {
            "sandbox_name": "sbx-seeddemo1",
            "state": "pending",
            "execution_target": "celesto_sandbox",
        }
        resp = client.post("/api/runs", json=payload)
        assert resp.status_code == 400

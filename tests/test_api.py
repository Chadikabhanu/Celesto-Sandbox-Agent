import os
import pytest
import httpx

BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8080")


@pytest.fixture
def client():
    with httpx.Client(base_url=BASE_URL, timeout=2.0) as c:
        try:
            resp = c.get("/health")
            if resp.status_code != 200:
                pytest.skip(f"API server at {BASE_URL} returned status {resp.status_code}")
        except Exception as e:
            pytest.skip(f"API server not reachable at {BASE_URL}: {e}")
        yield c


def test_health_check(client):
    """GET /health must return HTTP 200 and {'status': 'ok'}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_runs_includes_seed(client):
    """GET /api/runs must return JSON array containing seeded sbx-seeddemo1."""
    response = client.get("/api/runs")
    assert response.status_code == 200
    runs = response.json()
    assert isinstance(runs, list)
    assert len(runs) >= 1

    # Verify seed record fields
    seed = next((r for r in runs if r["sandbox_name"] == "sbx-seeddemo1"), None)
    assert seed is not None, "Seed record sbx-seeddemo1 was not found in database ledger"
    assert seed["state"] == "deleted"
    assert seed["execution_target"] == "celesto_sandbox"


def test_create_run_valid(client):
    """POST /api/runs with valid payload returns HTTP 201."""
    import uuid
    unique_suffix = uuid.uuid4().hex[:10]
    sandbox_name = f"sbx-{unique_suffix}"

    payload = {
        "sandbox_name": sandbox_name,
        "state": "pending",
        "execution_target": "celesto_sandbox",
        "task_id": "task-test-01",
        "metadata": {"test_run": True, "concurrency_slot": 1},
    }

    response = client.post("/api/runs", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["sandbox_name"] == sandbox_name
    assert data["state"] == "pending"
    assert data["execution_target"] == "celesto_sandbox"
    assert data["task_id"] == "task-test-01"
    assert data["metadata"] == {"test_run": True, "concurrency_slot": 1}
    assert "id" in data
    assert "created_at" in data

    # Verify run is now persisted in GET /api/runs
    list_resp = client.get("/api/runs")
    assert list_resp.status_code == 200
    all_runs = list_resp.json()
    assert any(r["sandbox_name"] == sandbox_name for r in all_runs)


@pytest.mark.parametrize(
    "invalid_name",
    [
        "invalid",                     # Missing sbx- prefix
        "sbx-123",                     # Too short (< 8 chars after prefix)
        "sbx-UPPERCASE123",            # Contains uppercase
        "sbx-special_char!",           # Invalid characters
        "host-machine",                # Bad prefix
        "",                            # Empty string
    ],
)
def test_reject_invalid_sandbox_name(client, invalid_name):
    """POST /api/runs with invalid sandbox_name must return HTTP 400."""
    payload = {
        "sandbox_name": invalid_name,
        "state": "pending",
        "execution_target": "celesto_sandbox",
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 400, f"Expected 400 for sandbox_name '{invalid_name}', got {response.status_code}"


@pytest.mark.parametrize(
    "invalid_state",
    [
        "invalid_state",
        "unknown",
        "active",
        "running_now",
        "12345",
    ],
)
def test_reject_invalid_state(client, invalid_state):
    """POST /api/runs with invalid state must return HTTP 400."""
    payload = {
        "sandbox_name": "sbx-validname123",
        "state": invalid_state,
        "execution_target": "celesto_sandbox",
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 400, f"Expected 400 for state '{invalid_state}', got {response.status_code}"


@pytest.mark.parametrize(
    "invalid_target",
    [
        "host_subprocess",
        "docker_host",
        "untrusted_vm",
        "bare_metal",
        "root_shell",
    ],
)
def test_reject_invalid_execution_target(client, invalid_target):
    """POST /api/runs with invalid execution_target must return HTTP 400."""
    payload = {
        "sandbox_name": "sbx-validname456",
        "state": "pending",
        "execution_target": invalid_target,
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 400, f"Expected 400 for execution_target '{invalid_target}', got {response.status_code}"


def test_reject_duplicate_sandbox_name(client):
    """POST /api/runs with duplicate sandbox_name must return HTTP 400."""
    payload = {
        "sandbox_name": "sbx-seeddemo1",  # Already present from seed
        "state": "pending",
        "execution_target": "celesto_sandbox",
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 400

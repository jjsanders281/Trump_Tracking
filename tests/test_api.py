import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Use a dedicated local test database file.
os.environ["DATABASE_URL"] = "sqlite:///./test_tracker.db"
os.environ["SEED_SAMPLE_DATA"] = "true"

from backend.app.main import app  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_search_returns_items(client: TestClient) -> None:
    response = client.get("/api/claims/search")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert len(payload["items"]) >= 1


def test_filter_by_topic(client: TestClient) -> None:
    response = client.get("/api/claims/search", params={"topic": "Healthcare"})
    assert response.status_code == 200
    payload = response.json()
    assert all(item["topic"] == "Healthcare" for item in payload["items"])


def teardown_module() -> None:
    db_file = Path("test_tracker.db")
    if db_file.exists():
        db_file.unlink()

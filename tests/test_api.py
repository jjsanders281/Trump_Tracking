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


def test_workflow_intake_factcheck_editorial_publish(client: TestClient) -> None:
    intake_payload = {
        "statement": {
            "occurred_at": "2026-02-23T12:00:00",
            "speaker": "Donald J. Trump",
            "venue": "Press Event",
            "quote": "WORKFLOW TEST QUOTE: A healthcare plan will be released this week.",
            "context": "Workflow test context.",
            "primary_source_url": "https://example.org/workflow-primary",
            "media_url": "https://example.org/workflow-video",
            "region": "US",
            "impact_score": 4,
        },
        "claim": {
            "claim_text": "WORKFLOW TEST CLAIM: A healthcare plan will be released this week.",
            "topic": "Healthcare",
            "claim_kind": "promise",
            "tags": ["workflow-test", "healthcare"],
        },
        "sources": [
            {
                "publisher": "AP",
                "url": "https://example.org/workflow-ap",
                "source_tier": 1,
                "is_primary": False,
            }
        ],
        "intake_note": "Created by API workflow test.",
    }

    intake_response = client.post("/api/workflow/intake", json=intake_payload)
    assert intake_response.status_code == 200
    intake_claim = intake_response.json()
    claim_id = intake_claim["id"]
    assert intake_claim["latest_assessment"] is None

    fact_check_queue_response = client.get("/api/workflow/queues/fact_check", params={"limit": 200})
    assert fact_check_queue_response.status_code == 200
    fact_check_ids = [item["id"] for item in fact_check_queue_response.json()["items"]]
    assert claim_id in fact_check_ids

    fact_check_payload = {
        "verdict": "false",
        "rationale": (
            "Evidence:\n"
            "- The primary source and corroborating records for this test claim show no released healthcare plan in the stated week.\n"
            "- Timeline checks in the provided sources do not contain the promised publication event.\n\n"
            "Why This Is False:\n"
            "- The claim predicts a release inside a specific timeframe, but the source trail contains no such release.\n"
            "- Because the event did not occur in the claimed window, the statement fails on its core factual condition.\n\n"
            "Shut Down False Argument:\n"
            "- Saying a plan was discussed is not equivalent to proving the promised release occurred.\n"
            "- The evidentiary burden is publication in the timeframe, and the cited records do not show it."
        ),
        "reviewer_primary": "fact_checker_test",
        "source_tier_used": 1,
        "sources": [
            {
                "publisher": "Reuters",
                "url": "https://example.org/workflow-reuters",
                "source_tier": 1,
                "is_primary": False,
            }
        ],
        "contradiction_claim_ids": [],
        "note": "Submitted from workflow test.",
    }

    fact_check_response = client.post(f"/api/workflow/fact-check/{claim_id}", json=fact_check_payload)
    assert fact_check_response.status_code == 200
    fact_checked_claim = fact_check_response.json()
    assert fact_checked_claim["latest_assessment"]["publish_status"] == "pending"
    assert fact_checked_claim["latest_assessment"]["reviewer_primary"] == "fact_checker_test"

    editorial_queue_response = client.get("/api/workflow/queues/editorial", params={"limit": 200})
    assert editorial_queue_response.status_code == 200
    editorial_ids = [item["id"] for item in editorial_queue_response.json()["items"]]
    assert claim_id in editorial_ids

    editorial_payload = {
        "publish_status": "verified",
        "reviewer_secondary": "editor_test",
        "note": "Approved in workflow test.",
    }

    editorial_response = client.post(f"/api/workflow/editorial/{claim_id}", json=editorial_payload)
    assert editorial_response.status_code == 200
    published_claim = editorial_response.json()
    assert published_claim["latest_assessment"]["publish_status"] == "verified"
    assert published_claim["latest_assessment"]["reviewer_secondary"] == "editor_test"

    search_response = client.get(
        "/api/claims/search",
        params={"q": "WORKFLOW TEST CLAIM", "verified_only": True, "limit": 200},
    )
    assert search_response.status_code == 200
    search_ids = [item["id"] for item in search_response.json()["items"]]
    assert claim_id in search_ids

    summary_response = client.get("/api/workflow/summary")
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert {"fact_check", "editorial", "verified", "rejected"} <= set(summary.keys())


def teardown_module() -> None:
    db_file = Path("test_tracker.db")
    if db_file.exists():
        db_file.unlink()

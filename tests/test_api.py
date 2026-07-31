from __future__ import annotations

from fastapi.testclient import TestClient

from self_improving_memory_augmented_agent.api import create_app


def test_health_endpoint_lists_memory_tools() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert "memory_store" in response.json()["tools"]


def test_run_endpoint_retrieves_memory() -> None:
    client = TestClient(create_app())
    client.post(
        "/v1/agent/run",
        json={
            "prompt": "remember semantic: For latency incidents, lead with customer impact.",
            "auto_approve": True,
        },
    )
    response = client.post("/v1/agent/run", json={"prompt": "retrieve latency incidents"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert "customer impact" in payload["final_answer"]

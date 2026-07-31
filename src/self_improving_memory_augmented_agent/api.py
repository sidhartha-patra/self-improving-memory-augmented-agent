from __future__ import annotations

from fastapi import FastAPI

from .harness import AgentHarness, build_default_harness
from .models import AgentRequest, AgentResponse


def create_app(harness: AgentHarness | None = None) -> FastAPI:
    app = FastAPI(title="Self Improving Memory Augmented Agent", version="0.1.0")
    runtime_harness = harness or build_default_harness()

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "tools": [capability.name for capability in runtime_harness.capabilities()],
        }

    @app.post("/v1/agent/run", response_model=AgentResponse)
    def run_agent(request: AgentRequest) -> AgentResponse:
        return runtime_harness.run(request)

    return app


app = create_app()

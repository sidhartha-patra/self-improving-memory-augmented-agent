from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SELF_IMPROVING_MEMORY_AUGMENTED_AGENT_",
        extra="ignore",
    )

    app_name: str = "Self Improving Memory Augmented Agent"
    environment: str = "local"
    max_iterations: int = Field(default=4, ge=1, le=20)
    max_execution_seconds: float = Field(default=5.0, gt=0.0, le=60.0)
    tool_timeout_seconds: float = Field(default=1.0, gt=0.0, le=30.0)
    tool_retry_limit: int = Field(default=1, ge=0, le=3)
    circuit_breaker_threshold: int = Field(default=2, ge=1, le=10)
    workspace_root: Path = Field(default_factory=default_workspace_root)

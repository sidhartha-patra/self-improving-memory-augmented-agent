from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AgentStatus(StrEnum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    ITERATION_LIMIT = "iteration_limit"
    TIME_LIMIT = "time_limit"


class ToolCapability(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    side_effects: list[str] = Field(default_factory=list)


class AuditEvent(BaseModel):
    event_type: str
    severity: Literal["info", "warning", "error"] = "info"
    message: str
    trace_id: str
    occurred_at: datetime
    data: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    tool_name: str
    approved: bool
    reason: str


class StepRecord(BaseModel):
    iteration: int
    tool_name: str
    tool_arguments: dict[str, Any]
    tool_output: dict[str, Any]


class AgentRequest(BaseModel):
    prompt: str = Field(min_length=1)
    trace_id: str | None = None
    auto_approve: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    status: AgentStatus
    trace_id: str
    final_answer: str
    steps: list[StepRecord] = Field(default_factory=list)
    safety_findings: list[str] = Field(default_factory=list)
    approvals: list[ApprovalDecision] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)
    elapsed_ms: int = 0


class ModelDecision(BaseModel):
    kind: Literal["tool", "final"]
    rationale: str
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    final_answer: str | None = None


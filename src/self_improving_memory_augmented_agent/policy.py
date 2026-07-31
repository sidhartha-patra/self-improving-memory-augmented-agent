from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, Field

from .models import ApprovalDecision, RiskLevel, ToolCapability


class SafetyInspection(BaseModel):
    allowed: bool
    findings: list[str] = Field(default_factory=list)


class SafetyPolicy:
    def __init__(self) -> None:
        self._patterns: dict[str, str] = {
            "ignore previous instructions": (
                "prompt injection attempt to override trusted instructions"
            ),
            "reveal system prompt": "attempt to exfiltrate hidden instructions",
            "send credentials": "attempt to exfiltrate secrets",
            "disable safety": "attempt to disable safety controls",
            "bypass approval": "attempt to bypass approval gates",
        }

    def inspect_prompt(self, prompt: str) -> SafetyInspection:
        lowered = prompt.lower()
        findings = [detail for needle, detail in self._patterns.items() if needle in lowered]
        return SafetyInspection(allowed=not findings, findings=findings)

    def should_require_approval(self, capability: ToolCapability) -> bool:
        return capability.requires_approval or capability.risk_level == RiskLevel.HIGH

    def contains_untrusted_instruction(self, snippets: Iterable[str]) -> bool:
        lowered = " ".join(snippets).lower()
        return any(needle in lowered for needle in self._patterns)


class StaticApprovalGate:
    def __init__(self, approved_tools: set[str] | None = None) -> None:
        self._approved_tools = approved_tools or set()

    def decide(self, capability: ToolCapability, auto_approve: bool) -> ApprovalDecision:
        if auto_approve or capability.name in self._approved_tools:
            return ApprovalDecision(
                tool_name=capability.name,
                approved=True,
                reason="approval granted",
            )
        return ApprovalDecision(
            tool_name=capability.name,
            approved=False,
            reason="approval required for risky action",
        )

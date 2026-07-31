from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

from .audit import AuditTrail
from .model import FakeDeterministicModel
from .models import (
    AgentRequest,
    AgentResponse,
    AgentStatus,
    ApprovalDecision,
    StepRecord,
    ToolCapability,
)
from .policy import SafetyPolicy, StaticApprovalGate
from .settings import AppSettings
from .tools import BaseTool, ToolContext, ToolExecutionError, build_default_tools


class AgentHarness:
    def __init__(
        self,
        *,
        settings: AppSettings | None = None,
        tools: dict[str, BaseTool] | None = None,
        model: FakeDeterministicModel | None = None,
        approval_gate: StaticApprovalGate | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.tools = tools or build_default_tools()
        self.model = model or FakeDeterministicModel()
        self.policy = SafetyPolicy()
        self.approval_gate = approval_gate or StaticApprovalGate()
        self._failure_counts = {name: 0 for name in self.tools}

    def capabilities(self) -> list[ToolCapability]:
        return [tool.capability for tool in self.tools.values()]

    def _invoke_with_timeout(
        self,
        tool: BaseTool,
        arguments: dict[str, object],
        trace_id: str,
    ) -> dict[str, object]:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(
            tool.invoke,
            arguments,
            ToolContext(workspace_root=self.settings.workspace_root, trace_id=trace_id),
        )
        try:
            return future.result(timeout=self.settings.tool_timeout_seconds)
        except FuturesTimeoutError as exc:
            future.cancel()
            raise ToolExecutionError(
                f"tool timed out after {self.settings.tool_timeout_seconds} seconds"
            ) from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _execute_tool(
        self,
        tool: BaseTool,
        arguments: dict[str, object],
        audit: AuditTrail,
        trace_id: str,
    ) -> dict[str, object]:
        if self._failure_counts[tool.capability.name] >= self.settings.circuit_breaker_threshold:
            raise ToolExecutionError(f"circuit open for {tool.capability.name}")

        attempts = self.settings.tool_retry_limit + 1
        last_error: ToolExecutionError | None = None
        for attempt in range(1, attempts + 1):
            try:
                result = self._invoke_with_timeout(tool, arguments, trace_id)
                self._failure_counts[tool.capability.name] = 0
                return result
            except ToolExecutionError as exc:
                self._failure_counts[tool.capability.name] += 1
                last_error = exc
                audit.emit(
                    "tool.failure",
                    f"{tool.capability.name} failed on attempt {attempt}",
                    severity="warning",
                    data={"tool_name": tool.capability.name, "attempt": attempt, "error": str(exc)},
                )
                if attempt < attempts:
                    audit.emit(
                        "tool.retry",
                        f"retrying {tool.capability.name}",
                        data={"tool_name": tool.capability.name, "next_attempt": attempt + 1},
                    )
        if last_error is None:
            raise ToolExecutionError("tool execution failed without a captured exception")
        raise last_error

    def run(self, request: AgentRequest) -> AgentResponse:
        trace_id = request.trace_id or uuid.uuid4().hex
        audit = AuditTrail(trace_id)
        start = time.monotonic()
        approvals: list[ApprovalDecision] = []
        steps: list[StepRecord] = []

        audit.emit("request.received", "received agent request", data={"prompt": request.prompt})
        safety = self.policy.inspect_prompt(request.prompt)
        if not safety.allowed:
            audit.emit(
                "request.blocked",
                "blocked due to prompt injection findings",
                severity="warning",
            )
            return AgentResponse(
                status=AgentStatus.BLOCKED,
                trace_id=trace_id,
                final_answer="Request blocked by prompt injection safety policy.",
                safety_findings=safety.findings,
                approvals=approvals,
                audit_events=audit.events,
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )

        for iteration in range(1, self.settings.max_iterations + 1):
            if time.monotonic() - start > self.settings.max_execution_seconds:
                audit.emit("run.timed_out", "overall execution budget exhausted", severity="error")
                return AgentResponse(
                    status=AgentStatus.TIME_LIMIT,
                    trace_id=trace_id,
                    final_answer="Execution stopped because the overall time budget was exhausted.",
                    steps=steps,
                    approvals=approvals,
                    audit_events=audit.events,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )

            decision = self.model.next_decision(request.prompt, steps, self.capabilities())
            audit.emit("model.decision", decision.rationale, data=decision.model_dump())

            if decision.kind == "final":
                return AgentResponse(
                    status=AgentStatus.COMPLETED,
                    trace_id=trace_id,
                    final_answer=decision.final_answer or "Completed without a final answer.",
                    steps=steps,
                    approvals=approvals,
                    audit_events=audit.events,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )

            if decision.tool_name is None:
                audit.emit(
                    "run.failed",
                    "model selected tool mode without a tool name",
                    severity="error",
                )
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    trace_id=trace_id,
                    final_answer="Model selected an invalid tool action.",
                    steps=steps,
                    approvals=approvals,
                    audit_events=audit.events,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )

            tool = self.tools[decision.tool_name]
            capability = tool.capability
            if self.policy.should_require_approval(capability):
                approval = self.approval_gate.decide(capability, request.auto_approve)
                approvals.append(approval)
                audit.emit("approval.checked", approval.reason, data=approval.model_dump())
                if not approval.approved:
                    return AgentResponse(
                        status=AgentStatus.BLOCKED,
                        trace_id=trace_id,
                        final_answer="Request requires approval before the risky action can run.",
                        steps=steps,
                        approvals=approvals,
                        audit_events=audit.events,
                        elapsed_ms=int((time.monotonic() - start) * 1000),
                    )

            try:
                output = self._execute_tool(tool, decision.arguments, audit, trace_id)
            except ToolExecutionError as exc:
                audit.emit("run.failed", str(exc), severity="error")
                return AgentResponse(
                    status=AgentStatus.FAILED,
                    trace_id=trace_id,
                    final_answer=f"Tool execution failed safely: {exc}",
                    steps=steps,
                    approvals=approvals,
                    audit_events=audit.events,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )

            steps.append(
                StepRecord(
                    iteration=iteration,
                    tool_name=decision.tool_name,
                    tool_arguments=decision.arguments,
                    tool_output=output,
                )
            )
            audit.emit(
                "tool.succeeded",
                f"{decision.tool_name} completed",
                data={"tool_name": decision.tool_name},
            )

        audit.emit("run.iteration_limit", "iteration limit reached", severity="warning")
        return AgentResponse(
            status=AgentStatus.ITERATION_LIMIT,
            trace_id=trace_id,
            final_answer="Execution stopped because the iteration limit was reached.",
            steps=steps,
            approvals=approvals,
            audit_events=audit.events,
            elapsed_ms=int((time.monotonic() - start) * 1000),
        )


def build_default_harness() -> AgentHarness:
    return AgentHarness()

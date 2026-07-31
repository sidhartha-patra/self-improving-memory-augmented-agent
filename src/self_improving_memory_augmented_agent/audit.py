from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from .models import AuditEvent


class AuditTrail:
    def __init__(self, trace_id: str) -> None:
        self.trace_id = trace_id
        self.events: list[AuditEvent] = []

    def emit(
        self,
        event_type: str,
        message: str,
        *,
        severity: Literal["info", "warning", "error"] = "info",
        data: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            AuditEvent(
                event_type=event_type,
                severity=severity,
                message=message,
                trace_id=self.trace_id,
                occurred_at=datetime.now(UTC),
                data=data or {},
            )
        )

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from .demo_data import SAMPLE_MEMORY_GUIDANCE
from .models import RiskLevel, ToolCapability


class ToolExecutionError(RuntimeError):
    pass


@dataclass(slots=True)
class ToolContext:
    workspace_root: Path
    trace_id: str


class BaseTool:
    input_model: type[BaseModel]
    output_model: type[BaseModel]

    def __init__(
        self,
        *,
        name: str,
        description: str,
        input_model: type[BaseModel],
        output_model: type[BaseModel],
        risk_level: RiskLevel = RiskLevel.LOW,
        requires_approval: bool = False,
        side_effects: list[str] | None = None,
    ) -> None:
        self.input_model = input_model
        self.output_model = output_model
        self.capability = ToolCapability(
            name=name,
            description=description,
            input_schema=input_model.model_json_schema(),
            output_schema=output_model.model_json_schema(),
            risk_level=risk_level,
            requires_approval=requires_approval,
            side_effects=side_effects or [],
        )

    def execute(self, payload: BaseModel, context: ToolContext) -> BaseModel:
        raise NotImplementedError

    def invoke(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        payload = self.input_model.model_validate(arguments)
        result = self.execute(payload, context)
        return result.model_dump()


class MemoryStoreInput(BaseModel):
    kind: Literal["episodic", "semantic"]
    content: str = Field(min_length=5)
    tags: list[str] = Field(default_factory=list)
    retention_days: int = Field(default=30, ge=0, le=365)


class MemoryStoreOutput(BaseModel):
    memory_id: str
    kind: str
    expires_at: str
    stored: bool


class MemorySearchInput(BaseModel):
    query: str = Field(min_length=2)
    limit: int = Field(default=3, ge=1, le=10)


class MemoryMatch(BaseModel):
    memory_id: str
    kind: str
    content: str
    tags: list[str]
    score: int
    expires_at: str


class MemorySearchOutput(BaseModel):
    matches: list[MemoryMatch]
    answer: str


class ReflectionInput(BaseModel):
    query: str = Field(min_length=2)


class ReflectionOutput(BaseModel):
    answer: str
    matched_memory_ids: list[str]
    retention_note: str


class ForgetInput(BaseModel):
    include_all_expired: bool = True


class ForgetOutput(BaseModel):
    deleted_count: int
    remaining_count: int


class KnowledgeInput(BaseModel):
    query: str


class KnowledgeOutput(BaseModel):
    answer: str


class MemoryRepository:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.db_path = workspace_root / "runtime-output" / "memory-store.sqlite3"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_items (
                    memory_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )

    def store(
        self,
        *,
        kind: str,
        content: str,
        tags: list[str],
        retention_days: int,
    ) -> MemoryStoreOutput:
        self._reject_sensitive(content)
        memory_id = f"mem-{uuid4().hex[:10]}"
        created_at = datetime.now(UTC)
        expires_at = created_at + timedelta(days=retention_days)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_items (
                    memory_id,
                    kind,
                    content,
                    tags_json,
                    created_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    kind,
                    content,
                    json.dumps(tags),
                    created_at.isoformat(),
                    expires_at.isoformat(),
                ),
            )
        return MemoryStoreOutput(
            memory_id=memory_id,
            kind=kind,
            expires_at=expires_at.isoformat(),
            stored=True,
        )

    def search(self, *, query: str, limit: int) -> dict[str, Any]:
        rows = self._active_rows()
        tokens = self._tokens(query)
        ranked: list[dict[str, Any]] = []
        for row in rows:
            tags = json.loads(str(row["tags_json"]))
            haystack = f"{row['content']} {' '.join(tags)}".lower()
            score = sum(1 for token in tokens if token in haystack)
            if score > 0:
                ranked.append(
                    {
                        "memory_id": str(row["memory_id"]),
                        "kind": str(row["kind"]),
                        "content": str(row["content"]),
                        "tags": [str(tag) for tag in tags],
                        "score": score,
                        "expires_at": str(row["expires_at"]),
                    }
                )
        ranked.sort(key=lambda item: (item["score"], item["expires_at"]), reverse=True)
        top = ranked[:limit]
        if not top:
            return {
                "matches": [],
                "answer": "No retained memory matched the query.",
            }
        answer = "Retrieved memory guidance: " + " | ".join(item["content"] for item in top)
        return {"matches": top, "answer": answer}

    def reflect(self, *, query: str) -> dict[str, Any]:
        search_result = self.search(query=query, limit=5)
        rows = self._active_rows()
        soon_to_expire = sum(
            1
            for row in rows
            if datetime.fromisoformat(str(row["expires_at"]))
            <= datetime.now(UTC) + timedelta(days=7)
        )
        matched_ids = [str(match["memory_id"]) for match in search_result["matches"]]
        if matched_ids:
            answer = (
                "Reflection: reuse the retained guidance, cite the most relevant memory first, "
                "and prune stale memories that no longer improve answers."
            )
        else:
            answer = (
                "Reflection: there is no matching retained memory yet, so add a reviewed episodic "
                "or semantic memory before relying on adaptation."
            )
        return {
            "answer": answer,
            "matched_memory_ids": matched_ids,
            "retention_note": f"{soon_to_expire} active memories expire within 7 days.",
        }

    def forget_expired(self) -> dict[str, int]:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            deleted = connection.execute(
                "DELETE FROM memory_items WHERE expires_at <= ?",
                (now,),
            ).rowcount
            remaining = connection.execute(
                "SELECT COUNT(*) FROM memory_items WHERE expires_at > ?",
                (now,),
            ).fetchone()[0]
        return {"deleted_count": int(deleted), "remaining_count": int(remaining)}

    def _active_rows(self) -> list[sqlite3.Row]:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT memory_id, kind, content, tags_json, created_at, expires_at
                    FROM memory_items
                    WHERE expires_at > ?
                    ORDER BY created_at DESC
                    """,
                    (now,),
                )
            )

    def _reject_sensitive(self, content: str) -> None:
        patterns = (
            r"password\s*[:=]",
            r"api[_-]?key",
            r"private[_ -]?key",
            r"secret",
            r"token",
            r"\b\d{3}-\d{2}-\d{4}\b",
            r"AKIA[0-9A-Z]{16}",
        )
        lowered = content.lower()
        if any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in patterns):
            raise ToolExecutionError("sensitive data was rejected and not stored in memory")

    def _tokens(self, text: str) -> set[str]:
        stop_words = {"the", "and", "for", "that", "with", "from", "this", "into"}
        return {
            token
            for token in re.findall(r"[a-z0-9-]+", text.lower())
            if len(token) > 2 and token not in stop_words
        }


class MemoryStoreTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="memory_store",
            description="Persist an approved episodic or semantic memory in the local store.",
            input_model=MemoryStoreInput,
            output_model=MemoryStoreOutput,
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            side_effects=["local sqlite memory write"],
        )

    def execute(self, payload: BaseModel, context: ToolContext) -> BaseModel:
        parsed = MemoryStoreInput.model_validate(payload)
        repository = MemoryRepository(context.workspace_root)
        return repository.store(
            kind=parsed.kind,
            content=parsed.content,
            tags=parsed.tags,
            retention_days=parsed.retention_days,
        )


class MemorySearchTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="memory_search",
            description="Retrieve active memories relevant to a query.",
            input_model=MemorySearchInput,
            output_model=MemorySearchOutput,
        )

    def execute(self, payload: BaseModel, context: ToolContext) -> BaseModel:
        parsed = MemorySearchInput.model_validate(payload)
        repository = MemoryRepository(context.workspace_root)
        return MemorySearchOutput(**repository.search(query=parsed.query, limit=parsed.limit))


class MemoryReflectTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="memory_reflect",
            description="Summarize how retained memories should improve future answers.",
            input_model=ReflectionInput,
            output_model=ReflectionOutput,
        )

    def execute(self, payload: BaseModel, context: ToolContext) -> BaseModel:
        parsed = ReflectionInput.model_validate(payload)
        repository = MemoryRepository(context.workspace_root)
        return ReflectionOutput(**repository.reflect(query=parsed.query))


class MemoryForgetTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="memory_forget_expired",
            description="Delete expired memories according to retention policy.",
            input_model=ForgetInput,
            output_model=ForgetOutput,
            risk_level=RiskLevel.MEDIUM,
            side_effects=["local sqlite memory delete"],
        )

    def execute(self, payload: BaseModel, context: ToolContext) -> BaseModel:
        repository = MemoryRepository(context.workspace_root)
        return ForgetOutput(**repository.forget_expired())


class RepoKnowledgeTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="repo_knowledge",
            description="Explain the memory, retention, and privacy model.",
            input_model=KnowledgeInput,
            output_model=KnowledgeOutput,
        )

    def execute(self, payload: BaseModel, context: ToolContext) -> BaseModel:
        return KnowledgeOutput(
            answer=(
                f"{SAMPLE_MEMORY_GUIDANCE['purpose']} "
                f"{SAMPLE_MEMORY_GUIDANCE['privacy']}"
            )
        )


class FailingTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="failing_tool",
            description="Tool used by tests to simulate failures.",
            input_model=KnowledgeInput,
            output_model=KnowledgeOutput,
        )

    def execute(self, payload: BaseModel, context: ToolContext) -> BaseModel:
        raise ToolExecutionError("simulated tool failure")


class SlowTool(BaseTool):
    def __init__(self, delay_seconds: float) -> None:
        super().__init__(
            name="slow_tool",
            description="Tool used by tests to simulate timeouts.",
            input_model=KnowledgeInput,
            output_model=KnowledgeOutput,
        )
        self.delay_seconds = delay_seconds

    def execute(self, payload: BaseModel, context: ToolContext) -> BaseModel:
        import time

        time.sleep(self.delay_seconds)
        return KnowledgeOutput(answer="slow tool completed")


def build_default_tools() -> dict[str, BaseTool]:
    tools: list[BaseTool] = [
        MemoryStoreTool(),
        MemorySearchTool(),
        MemoryReflectTool(),
        MemoryForgetTool(),
        RepoKnowledgeTool(),
    ]
    return {tool.capability.name: tool for tool in tools}

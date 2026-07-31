from __future__ import annotations

import re
from collections.abc import Iterable

from .models import ModelDecision, StepRecord, ToolCapability


def _extract_memory_payload(prompt: str) -> tuple[str, str, list[str], int]:
    kind = "semantic"
    if "episodic" in prompt.lower() or "episode" in prompt.lower():
        kind = "episodic"
    retention_match = re.search(r"retention\s+(\d+)", prompt, flags=re.IGNORECASE)
    retention_days = int(retention_match.group(1)) if retention_match else 30
    tag_match = re.search(r"tags\s*[:=]\s*([\w,\s-]+)", prompt, flags=re.IGNORECASE)
    tags = [tag.strip() for tag in tag_match.group(1).split(",")] if tag_match else []
    content_match = re.search(
        r"(?:remember|store memory|store)\s*(?:that)?\s*[:=]?\s*(.+)",
        prompt,
        flags=re.IGNORECASE,
    )
    content = content_match.group(1).strip() if content_match else prompt.strip()
    return kind, content, [tag for tag in tags if tag], retention_days


class FakeDeterministicModel:
    def next_decision(
        self,
        prompt: str,
        steps: list[StepRecord],
        capabilities: Iterable[ToolCapability],
    ) -> ModelDecision:
        if steps:
            last = steps[-1]
            if last.tool_name == "repo_knowledge":
                return ModelDecision(
                    kind="final",
                    rationale="repo explanation ready",
                    final_answer=str(last.tool_output["answer"]),
                )
            if last.tool_name == "memory_store":
                return ModelDecision(
                    kind="final",
                    rationale="memory checkpoint stored",
                    final_answer=(
                        f"Stored {last.tool_output['kind']} memory {last.tool_output['memory_id']} "
                        f"until {last.tool_output['expires_at']}."
                    ),
                )
            if last.tool_name == "memory_search":
                return ModelDecision(
                    kind="final",
                    rationale="retrieval complete",
                    final_answer=str(last.tool_output["answer"]),
                )
            if last.tool_name == "memory_reflect":
                return ModelDecision(
                    kind="final",
                    rationale="reflection complete",
                    final_answer=(
                        f"{last.tool_output['answer']} {last.tool_output['retention_note']}"
                    ),
                )
            if last.tool_name == "memory_forget_expired":
                return ModelDecision(
                    kind="final",
                    rationale="retention cleanup complete",
                    final_answer=(
                        f"Deleted {last.tool_output['deleted_count']} expired memories. "
                        f"{last.tool_output['remaining_count']} active memories remain."
                    ),
                )

        lowered = prompt.lower()
        if "purpose" in lowered or "what is this repo" in lowered or "explain" in lowered:
            return ModelDecision(
                kind="tool",
                rationale="return grounded repository purpose",
                tool_name="repo_knowledge",
                arguments={"query": prompt},
            )
        if "forget expired" in lowered or "cleanup memories" in lowered:
            return ModelDecision(
                kind="tool",
                rationale="apply retention cleanup",
                tool_name="memory_forget_expired",
                arguments={"include_all_expired": True},
            )
        if "reflect" in lowered:
            query = prompt.split("reflect", maxsplit=1)[-1].strip() or "memory quality"
            return ModelDecision(
                kind="tool",
                rationale="summarize reflective learning",
                tool_name="memory_reflect",
                arguments={"query": query},
            )
        if "remember" in lowered or "store memory" in lowered or lowered.startswith("store "):
            kind, content, tags, retention_days = _extract_memory_payload(prompt)
            return ModelDecision(
                kind="tool",
                rationale="persist reviewed memory checkpoint",
                tool_name="memory_store",
                arguments={
                    "kind": kind,
                    "content": content,
                    "tags": tags,
                    "retention_days": retention_days,
                },
            )
        query = prompt
        for prefix in ("retrieve", "recall", "search memory", "what do we know about"):
            if lowered.startswith(prefix):
                query = prompt[len(prefix) :].strip(" :")
                break
        return ModelDecision(
            kind="tool",
            rationale="retrieve retained memory",
            tool_name="memory_search",
            arguments={"query": query or prompt, "limit": 3},
        )

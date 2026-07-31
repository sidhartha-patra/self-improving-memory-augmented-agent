from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from .harness import build_default_harness
from .models import AgentRequest, AgentResponse, AgentStatus


class EvalCase(BaseModel):
    id: str
    prompt: str
    expected_status: AgentStatus
    expected_substrings: list[str] = Field(default_factory=list)
    auto_approve: bool = False


class EvalResult(BaseModel):
    id: str
    passed: bool
    observed_status: AgentStatus
    final_answer: str


class EvalSummary(BaseModel):
    passed: int
    total: int
    results: list[EvalResult]


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def dataset_path() -> Path:
    return project_root() / "evals" / "dataset.jsonl"


def load_cases(path: Path | None = None) -> list[EvalCase]:
    source = path or dataset_path()
    lines = [line for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [EvalCase.model_validate_json(line) for line in lines]


def evaluate_case(case: EvalCase) -> EvalResult:
    harness = build_default_harness()
    response: AgentResponse = harness.run(
        AgentRequest(prompt=case.prompt, auto_approve=case.auto_approve)
    )
    passed = response.status == case.expected_status and all(
        needle.lower() in response.final_answer.lower() for needle in case.expected_substrings
    )
    return EvalResult(
        id=case.id,
        passed=passed,
        observed_status=response.status,
        final_answer=response.final_answer,
    )


def run_evals(path: Path | None = None) -> EvalSummary:
    memory_db = project_root() / "runtime-output" / "memory-store.sqlite3"
    if memory_db.exists():
        memory_db.unlink()
    results = [evaluate_case(case) for case in load_cases(path)]
    summary = EvalSummary(
        passed=sum(1 for result in results if result.passed),
        total=len(results),
        results=results,
    )
    (project_root() / "evals" / "latest-results.json").write_text(
        summary.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    summary = run_evals()
    print(summary.model_dump_json(indent=2))
    return 0 if summary.passed == summary.total else 1

from __future__ import annotations

import json

import typer

from .evals import run_evals
from .harness import AgentHarness, build_default_harness
from .models import AgentRequest, AgentStatus

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)


@app.command()
def run(
    prompt: str,
    auto_approve: bool = typer.Option(False, help="Approve risky actions for this request."),
    json_output: bool = typer.Option(False, help="Render the full JSON response."),
) -> None:
    response = build_default_harness().run(AgentRequest(prompt=prompt, auto_approve=auto_approve))
    typer.echo(response.model_dump_json(indent=2) if json_output else response.final_answer)
    if response.status not in {AgentStatus.COMPLETED, AgentStatus.BLOCKED}:
        raise typer.Exit(code=1)


@app.command()
def capabilities() -> None:
    harness: AgentHarness = build_default_harness()
    payload = [capability.model_dump() for capability in harness.capabilities()]
    typer.echo(json.dumps(payload, indent=2))


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run("self_improving_memory_augmented_agent.api:app", host=host, port=port, reload=False)


@app.command("evals")
def evals_command() -> None:
    summary = run_evals()
    typer.echo(summary.model_dump_json(indent=2))
    if summary.passed != summary.total:
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

"""pipeline_watch CLI — thin wrapper around the LangGraph flow."""

from __future__ import annotations

import uuid

import typer

from pipeline_watch.graph import build_graph

app = typer.Typer(add_completion=False, help="CI/CD failure triage agent.")


@app.callback()
def _root() -> None:
    """Force typer to treat sub-commands as sub-commands (even when there's one)."""


@app.command()
def triage(
    run_id: str = typer.Option(..., "--run-id", help="GitHub Actions run id or fixture id."),
    source: str = typer.Option("fixture", "--source", help="fixture | github"),
) -> None:
    """Run the triage flow once and print the IncidentReport as JSON."""

    correlation_id = f"run-{run_id}-{uuid.uuid4().hex[:8]}"
    graph = build_graph()
    final_state = graph.invoke(
        {"run_id": run_id, "source": source, "correlation_id": correlation_id}
    )
    report = final_state["report"]
    typer.echo(report.model_dump_json(indent=2))


if __name__ == "__main__":
    app()

"""pipeline_watch CLI — thin wrapper around the LangGraph flow."""

from __future__ import annotations

import os
import uuid

import typer

from pipeline_watch.graph import build_graph
from pipeline_watch.observability import configure, get_logger, get_tracer

app = typer.Typer(add_completion=False, help="CI/CD failure triage agent.")


@app.callback()
def _root() -> None:
    """Force typer to treat sub-commands as sub-commands (even when there's one)."""


@app.command()
def triage(
    run_id: str = typer.Option(..., "--run-id", help="GitHub Actions run id or fixture id."),
    source: str = typer.Option("fixture", "--source", help="fixture | github"),
    repository: str = typer.Option(
        "",
        "--repository",
        help="owner/name, required when --source=github (or set GITHUB_REPO).",
    ),
    log_level: str = typer.Option(
        os.environ.get("PW_LOG_LEVEL", "INFO"),
        "--log-level",
        help="DEBUG | INFO | WARNING | ERROR",
    ),
) -> None:
    """Run the triage flow once and print the IncidentReport as JSON."""

    configure(
        log_level=log_level,
        exporter=os.environ.get("PW_OTEL_EXPORTER", "console"),
        otlp_endpoint=os.environ.get("PW_OTLP_ENDPOINT"),
    )

    correlation_id = f"run-{run_id}-{uuid.uuid4().hex[:8]}"
    log = get_logger()
    tracer = get_tracer()

    log.info("triage.start", run_id=run_id, source=source, correlation_id=correlation_id)

    initial: dict = {
        "run_id": run_id,
        "source": source,
        "correlation_id": correlation_id,
    }
    if repository:
        initial["repository"] = repository

    graph = build_graph()
    with tracer.start_as_current_span("triage.run") as root_span:
        root_span.set_attribute("pw.correlation_id", correlation_id)
        root_span.set_attribute("pw.run_id", run_id)
        root_span.set_attribute("pw.source", source)
        final_state = graph.invoke(initial)

    report = final_state["report"]
    log.info(
        "triage.done",
        run_id=run_id,
        correlation_id=correlation_id,
        decision=final_state.get("decision"),
        severity=report.severity.value,
        is_flaky=report.flakiness.is_flaky,
    )
    typer.echo(report.model_dump_json(indent=2))


if __name__ == "__main__":
    app()

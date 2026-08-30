"""Observability tests — both signals share the same correlation_id.

Setup notes:
- Spans: `configure()` sets the SDK provider once; we then attach a
  SimpleSpanProcessor + InMemorySpanExporter to that same provider so tests
  see spans without racing with the console exporter.
- Logs:  structlog writes JSON to stdout via PrintLogger. We capture with
  pytest's `capsys` — stdlib `caplog` won't see it.
"""

from __future__ import annotations

import json

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from pipeline_watch.graph import build_graph
from pipeline_watch.observability import configure, get_logger, traced_node
from pipeline_watch.state import TriageState


@pytest.fixture
def in_memory_spans():
    """Attach an in-memory exporter to whatever tracer provider is active."""

    configure(log_level="INFO")  # idempotent; ensures an SDK provider exists
    exporter = InMemorySpanExporter()

    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        # Some other test may have called set_tracer_provider before us with
        # a no-op provider. Force one that supports processors.
        provider = TracerProvider()
        trace.set_tracer_provider(provider)

    provider.add_span_processor(SimpleSpanProcessor(exporter))
    yield exporter
    exporter.clear()


# ---------------------------------------------------------- unit tests --


def test_traced_node_emits_start_and_end_logs(capsys, in_memory_spans):
    configure(log_level="INFO")

    def dummy(state: TriageState) -> dict:
        return {"ok": True}

    wrapped = traced_node(dummy)
    wrapped({"run_id": "r1", "correlation_id": "cid-abc"})  # type: ignore[arg-type]

    output = capsys.readouterr().out
    assert "node.start" in output
    assert "node.end" in output
    assert "cid-abc" in output
    assert "dummy" in output


def test_traced_node_creates_span_with_correlation_attribute(in_memory_spans):
    def dummy(state: TriageState) -> dict:
        return {"ok": True}

    wrapped = traced_node(dummy)
    wrapped({"run_id": "r1", "correlation_id": "cid-xyz"})  # type: ignore[arg-type]

    spans = in_memory_spans.get_finished_spans()
    node_span = next(s for s in spans if s.name == "node.dummy")
    assert node_span.attributes["pw.correlation_id"] == "cid-xyz"
    assert node_span.attributes["pw.node"] == "dummy"


def test_traced_node_records_exception(in_memory_spans, capsys):
    configure(log_level="INFO")

    def boom(state: TriageState) -> dict:
        raise ValueError("simulated")

    wrapped = traced_node(boom)
    with pytest.raises(ValueError):
        wrapped({"run_id": "r", "correlation_id": "cid-err"})  # type: ignore[arg-type]

    spans = in_memory_spans.get_finished_spans()
    boom_span = next(s for s in spans if s.name == "node.boom")
    assert boom_span.status.status_code == trace.StatusCode.ERROR

    output = capsys.readouterr().out
    assert "node.error" in output


# --------------------------------------------------------- graph e2e --


def test_full_graph_run_emits_span_per_node(in_memory_spans):
    graph = build_graph()
    graph.invoke(
        {"run_id": "lint-fixture", "source": "fixture", "correlation_id": "cid-full"}
    )

    span_names = {s.name for s in in_memory_spans.get_finished_spans()}
    expected = {
        "node.fetch_run_context",
        "node.classify_failure",
        "node.retrieve_runbook",
        "node.estimate_flakiness",
        "node.synthesize_diagnosis",
        "node.decide_action",
        "node.persist_incident",
    }
    assert expected.issubset(span_names), f"missing spans: {expected - span_names}"


def test_correlation_id_flows_from_state_to_logs_and_spans(
    in_memory_spans, capsys
):
    configure(log_level="INFO")

    graph = build_graph()
    graph.invoke(
        {
            "run_id": "lint-fixture",
            "source": "fixture",
            "correlation_id": "cid-CORRELATION-TEST",
        }
    )

    # Present in every span
    for span in in_memory_spans.get_finished_spans():
        assert span.attributes["pw.correlation_id"] == "cid-CORRELATION-TEST"

    # Present in structlog JSON output
    output = capsys.readouterr().out
    assert "cid-CORRELATION-TEST" in output


def test_structlog_output_is_valid_json_per_line(capsys):
    configure(log_level="INFO")

    log = get_logger("test")
    log.info("marker.event", foo="bar", n=1)

    captured = capsys.readouterr().out
    marker_lines = [ln for ln in captured.splitlines() if "marker.event" in ln]
    assert marker_lines, "no matching log line captured"
    parsed = json.loads(marker_lines[-1])
    assert parsed["event"] == "marker.event"
    assert parsed["foo"] == "bar"
    assert parsed["n"] == 1

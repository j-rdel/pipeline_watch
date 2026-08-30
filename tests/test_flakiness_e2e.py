"""End-to-end flakiness detection: run the graph N times over the same
fixture and verify the estimator's counters + is_flaky flag evolve as
expected. Uses the autouse in-memory SQLite fixture from conftest.
"""

from __future__ import annotations

import pytest

from pipeline_watch.graph import build_graph


@pytest.fixture
def graph():
    return build_graph()


def _run(graph, run_id: str = "lint-fixture") -> dict:
    return graph.invoke(
        {"run_id": run_id, "source": "fixture", "correlation_id": f"cid-{run_id}"}
    )


def test_first_run_has_zero_prior_history(graph):
    final = _run(graph)
    fl = final["flakiness"]
    assert fl.similar_failures_7d == 0
    assert fl.total_runs_7d == 0
    assert fl.is_flaky is False


def test_second_run_sees_one_prior_similar(graph):
    _run(graph)
    final = _run(graph)
    fl = final["flakiness"]
    assert fl.similar_failures_7d == 1
    assert fl.total_runs_7d == 1
    assert fl.is_flaky is False, "one prior failure is not enough evidence"


def test_third_run_flips_is_flaky_on(graph):
    _run(graph)
    _run(graph)
    final = _run(graph)
    fl = final["flakiness"]
    assert fl.similar_failures_7d == 2
    assert fl.total_runs_7d == 2
    assert fl.score == 1.0
    assert fl.is_flaky is True

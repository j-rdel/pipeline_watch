"""LangGraph flow assembly for pipeline_watch.

Topology
--------

                       ┌───────────────────┐
                       │ fetch_run_context │
                       └─────────┬─────────┘
                                 │
                       ┌─────────┴─────────┐   (parallel super-step)
                       ▼                   ▼
             ┌─────────────────┐  ┌──────────────────┐
             │ classify_failure│  │ retrieve_runbook │
             └────────┬────────┘  └────────┬─────────┘
                      └──────────┬─────────┘  (fan-in: waits for both)
                                 ▼
                       ┌───────────────────┐
                       │ estimate_flakiness│
                       └─────────┬─────────┘
                                 ▼
                     ┌───────────────────────┐
                     │ synthesize_diagnosis  │
                     └───────────┬───────────┘
                                 ▼
                        ┌────────────────┐
                        │ decide_action  │  (writes state.decision)
                        └───┬────────┬───┘
                            │        │  (conditional edge on state.decision)
              "autofix" ────┘        └──── "notify_only"
                            │        │
                            ▼        │
                 ┌────────────────┐  │
                 │ propose_patch  │  │
                 └───────┬────────┘  │
                         ▼           │
                 ┌────────────────┐  │  PolicyGate may DOWNGRADE
                 │ enforce_policy │  │  autofix → notify_only when
                 └───┬────────┬───┘  │  path off-allowlist, injection
       "autofix" ────┘        └── "notify_only"
                    │                │
                    ▼                ▼
              ┌─────────┐   ┌────────────────┐
              │ open_pr │   │ notify_discord │
              └────┬────┘   └───────┬────────┘
                   └────────┬───────┘
                            ▼
                 ┌──────────────────┐
                 │ persist_incident │
                 └────────┬─────────┘
                          ▼
                        END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from pipeline_watch.nodes.classify_failure import classify_failure
from pipeline_watch.nodes.decide_action import decide_action, route_after_decide
from pipeline_watch.nodes.enforce_policy import enforce_policy, route_after_enforce
from pipeline_watch.nodes.estimate_flakiness import estimate_flakiness
from pipeline_watch.nodes.fetch_run_context import fetch_run_context
from pipeline_watch.nodes.notify_discord import notify_discord
from pipeline_watch.nodes.open_pr import open_pr
from pipeline_watch.nodes.persist_incident import persist_incident
from pipeline_watch.nodes.propose_patch import propose_patch
from pipeline_watch.nodes.retrieve_runbook import retrieve_runbook
from pipeline_watch.nodes.synthesize_diagnosis import synthesize_diagnosis
from pipeline_watch.state import TriageState


def build_graph():
    g = StateGraph(TriageState)

    g.add_node("fetch_run_context", fetch_run_context)
    g.add_node("classify_failure", classify_failure)
    g.add_node("retrieve_runbook", retrieve_runbook)
    g.add_node("estimate_flakiness", estimate_flakiness)
    g.add_node("synthesize_diagnosis", synthesize_diagnosis)
    g.add_node("decide_action", decide_action)
    g.add_node("propose_patch", propose_patch)
    g.add_node("enforce_policy", enforce_policy)
    g.add_node("open_pr", open_pr)
    g.add_node("notify_discord", notify_discord)
    g.add_node("persist_incident", persist_incident)

    g.add_edge(START, "fetch_run_context")

    # Parallel fan-out: both nodes scheduled in the same super-step.
    g.add_edge("fetch_run_context", "classify_failure")
    g.add_edge("fetch_run_context", "retrieve_runbook")

    # Fan-in: estimate_flakiness waits for BOTH parallel branches.
    g.add_edge("classify_failure", "estimate_flakiness")
    g.add_edge("retrieve_runbook", "estimate_flakiness")

    g.add_edge("estimate_flakiness", "synthesize_diagnosis")
    g.add_edge("synthesize_diagnosis", "decide_action")

    g.add_conditional_edges(
        "decide_action",
        route_after_decide,
        {"autofix": "propose_patch", "notify_only": "notify_discord"},
    )

    # autofix path funnels through the PolicyGate, which can downgrade to notify.
    g.add_edge("propose_patch", "enforce_policy")
    g.add_conditional_edges(
        "enforce_policy",
        route_after_enforce,
        {"autofix": "open_pr", "notify_only": "notify_discord"},
    )

    g.add_edge("open_pr", "persist_incident")
    g.add_edge("notify_discord", "persist_incident")
    g.add_edge("persist_incident", END)

    return g.compile()

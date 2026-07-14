"""Super Agent orchestrator — the entry point for reading this codebase.

WHAT THIS IS:
A LangGraph StateGraph wiring six specialized nodes into a linear pipeline:

    scrape -> prefilter -> analyze -> select -> generate_artifacts -> referral_notes

Each node is a plain function `(state, ...) -> state` living in its own module.
That's the whole trick: LangGraph passes one state dict (see state.py) from node
to node, and every node returns a NEW dict (`{**state, ...}`) instead of mutating
the one it received — which makes each stage independently testable (feed it a
dict, assert on the dict it returns) and the run history reproducible.

WHY THE STAGES ARE ORDERED THIS WAY (cheapest filter first):
  1. scrape     — free:   official APIs + hash dedup drop everything already seen
  2. prefilter  — cheap:  Gemini screens 30 jobs per call, drops obvious misfits
  3. analyze    — costly: Claude scores each survivor on six dimensions
  4. select     — free:   threshold gates + ranked cap (pure Python)
  5. generate   — most costly: two Claude calls per selected job
  6. referrals  — free:   emits a manual-lookup company list
Every stage exists to shrink the set the next, more expensive stage sees.

WHY `partial(..., db=db)`:
LangGraph calls nodes with the state only. Nodes that persist data also need the
repository, so we bind it at graph-build time. Passing the DB in (rather than
importing a global) keeps nodes unit-testable against a throwaway database.
"""
from __future__ import annotations

from functools import partial

from langgraph.graph import END, StateGraph

from careerconductor.db.repository import CareerConductorDB

from .artifact_generator import run_artifact_generation
from .analysis import run_analysis
from .prefilter_node import run_prefilter
from .referral_notes import run_referral_notes
from .scraping_node import run_scraping
from .selection import run_selection
from .state import CareerEngineState


def build_graph(db: CareerConductorDB):
    graph = StateGraph(CareerEngineState)

    graph.add_node("scrape", partial(run_scraping, db=db))
    graph.add_node("prefilter", run_prefilter)
    graph.add_node("analyze", partial(run_analysis, db=db))
    graph.add_node("select", run_selection)
    graph.add_node("generate_artifacts", partial(run_artifact_generation, db=db))
    graph.add_node("referral_notes", run_referral_notes)

    graph.set_entry_point("scrape")
    graph.add_edge("scrape", "prefilter")
    graph.add_edge("prefilter", "analyze")
    graph.add_edge("analyze", "select")
    graph.add_edge("select", "generate_artifacts")
    graph.add_edge("generate_artifacts", "referral_notes")
    graph.add_edge("referral_notes", END)

    return graph.compile()

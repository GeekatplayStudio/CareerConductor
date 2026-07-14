"""Super Agent orchestrator: wires scraping -> analysis -> selection -> artifacts -> referrals."""
from __future__ import annotations

from functools import partial

from langgraph.graph import END, StateGraph

from careerconductor.db.repository import CareerConductorDB

from .artifact_generator import run_artifact_generation
from .analysis import run_analysis
from .referral_notes import run_referral_notes
from .scraping_node import run_scraping
from .selection import run_selection
from .state import CareerEngineState


def build_graph(db: CareerConductorDB):
    graph = StateGraph(CareerEngineState)

    graph.add_node("scrape", partial(run_scraping, db=db))
    graph.add_node("analyze", partial(run_analysis, db=db))
    graph.add_node("select", run_selection)
    graph.add_node("generate_artifacts", partial(run_artifact_generation, db=db))
    graph.add_node("referral_notes", run_referral_notes)

    graph.set_entry_point("scrape")
    graph.add_edge("scrape", "analyze")
    graph.add_edge("analyze", "select")
    graph.add_edge("select", "generate_artifacts")
    graph.add_edge("generate_artifacts", "referral_notes")
    graph.add_edge("referral_notes", END)

    return graph.compile()

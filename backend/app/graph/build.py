"""Compile the stubbed Sentinel graph with a checkpointer and two interrupt gates."""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from . import nodes
from .state import SentinelState


def build_graph(checkpointer):
    g = StateGraph(SentinelState)

    g.add_node("discover", nodes.discover)
    g.add_node("list_managed", nodes.list_managed)
    g.add_node("reconcile", nodes.reconcile)
    g.add_node("assess", nodes.assess)
    g.add_node("prioritize", nodes.prioritize)
    g.add_node("plan", nodes.plan)
    g.add_node("gate_staging", nodes.gate_staging)
    g.add_node("stage", nodes.stage)
    g.add_node("gate_cutover", nodes.gate_cutover)
    g.add_node("cutover", nodes.cutover)
    g.add_node("report", nodes.report)

    g.add_edge(START, "discover")
    g.add_edge("discover", "list_managed")
    g.add_edge("list_managed", "reconcile")
    g.add_edge("reconcile", "assess")
    g.add_edge("assess", "prioritize")
    g.add_edge("prioritize", "plan")
    g.add_edge("plan", "gate_staging")
    g.add_edge("gate_staging", "stage")
    g.add_edge("stage", "gate_cutover")
    g.add_edge("gate_cutover", "cutover")
    g.add_edge("cutover", "report")
    g.add_edge("report", END)

    return g.compile(checkpointer=checkpointer)

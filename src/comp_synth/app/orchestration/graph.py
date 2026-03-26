from langgraph.graph import END, StateGraph

from comp_synth.app.orchestration.nodes import (
    deduplicate,
    enrich,
    fetch_sources,
    publish,
    summarize,
)
from comp_synth.app.orchestration.state import PipelineState


def build_pipeline() -> StateGraph:
    """构建内容聚合流水线"""
    graph = StateGraph(PipelineState)

    graph.add_node("fetch_sources", fetch_sources)
    graph.add_node("deduplicate", deduplicate)
    graph.add_node("summarize", summarize)
    graph.add_node("enrich", enrich)
    graph.add_node("publish", publish)

    graph.set_entry_point("fetch_sources")
    graph.add_edge("fetch_sources", "deduplicate")

    def should_continue(state: PipelineState) -> str:
        return "summarize" if state.get("new_items") else "end"

    graph.add_conditional_edges("deduplicate", should_continue, {
        "end": END,
        "summarize": "summarize",
    })
    graph.add_edge("summarize", "enrich")
    graph.add_edge("enrich", "publish")
    graph.add_edge("publish", END)

    return graph.compile()

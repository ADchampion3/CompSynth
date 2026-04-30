from pathlib import Path
from typing import Callable

from langgraph.graph import END, StateGraph

from comp_synth.config import settings
from comp_synth.orchestration.nodes import (
    deduplicate,
    enrich,
    fetch_sources,
    publish,
    summarize,
    use_last_digest,
)
from comp_synth.orchestration.state import PipelineState


def _has_last_digest() -> bool:
    output_dir = Path(settings.output_dir)
    return any(output_dir.glob("digest_*.md"))


def route_after_deduplicate(
    state: PipelineState,
    has_last_digest: Callable[[], bool] = _has_last_digest,
) -> str:
    if state.get("new_items", []):
        return "summarize"
    if has_last_digest():
        return "use_last_digest"
    return "end"


def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("fetch_sources", fetch_sources)
    graph.add_node("deduplicate", deduplicate)
    graph.add_node("summarize", summarize)
    graph.add_node("enrich", enrich)
    graph.add_node("use_last_digest", use_last_digest)
    graph.add_node("publish", publish)

    graph.set_entry_point("fetch_sources")
    graph.add_edge("fetch_sources", "deduplicate")
    graph.add_conditional_edges(
        "deduplicate",
        route_after_deduplicate,
        {
            "end": END,
            "summarize": "summarize",
            "use_last_digest": "use_last_digest",
        },
    )
    graph.add_edge("summarize", "enrich")
    graph.add_edge("enrich", "publish")
    graph.add_edge("use_last_digest", END)
    graph.add_edge("publish", END)

    return graph.compile()

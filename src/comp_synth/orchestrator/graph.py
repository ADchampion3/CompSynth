from pathlib import Path

from langgraph.graph import END, StateGraph

from comp_synth.config import settings
from comp_synth.orchestrator.nodes import (
    deduplicate,
    enrich,
    fetch_sources,
    publish,
    summarize,
)
from comp_synth.orchestrator.state import PipelineState


def _has_last_digest() -> bool:
    """检查是否有上一次的 digest 文件"""
    output_dir = Path(settings.output_dir)
    digest_files = list(output_dir.glob("digest_*.md"))
    return len(digest_files) > 0


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
        new_items = state.get("raw_items", [])
        if new_items:
            return "summarize"
        # 没有新内容但有上一次的 digest → 跳到 publish 复用
        if _has_last_digest():
            return "publish"
        return "end"

    graph.add_conditional_edges("deduplicate", should_continue, {
        "end": END,
        "summarize": "summarize",
        "publish": "publish",
    })
    graph.add_edge("summarize", "enrich")
    graph.add_edge("enrich", "publish")
    graph.add_edge("publish", END)

    return graph.compile()

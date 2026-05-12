from pathlib import Path
from typing import Callable

from comp_synth.config import settings
from comp_synth.orchestration.nodes import (
    deduplicate,
    fetch_sources,
    notify,
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


def default_pipeline_state() -> PipelineState:
    return {
        "sources": [],
        "raw_items": [],
        "new_items": [],
        "topic_groups": [],
        "report": "",
        "publish_results": {},
        "notification_results": [],
        "errors": [],
        "content_manager": None,
    }


async def run_pipeline(initial_state: PipelineState | None = None) -> PipelineState:
    state = default_pipeline_state()
    if initial_state:
        state.update(initial_state)

    state.update(await fetch_sources(state))
    state.update(await deduplicate(state))

    route = route_after_deduplicate(state)
    if route == "end":
        return state
    if route == "use_last_digest":
        state.update(use_last_digest(state))
        return state

    state.update(await summarize(state))
    state.update(await publish(state))
    state.update(await notify(state))
    return state

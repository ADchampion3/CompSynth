from typing import TypedDict

from comp_synth.orchestration.content_manager import ContentManager
from comp_synth.schema.content_item import ContentItem


class PipelineState(TypedDict):
    """Plain async pipeline state definition."""

    sources: list[dict]
    raw_items: list[ContentItem]
    new_items: list[ContentItem]
    report: str
    publish_results: dict
    notification_results: list[dict]
    errors: list[str]
    content_manager: ContentManager | None

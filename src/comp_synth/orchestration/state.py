from typing import TypedDict

from comp_synth.orchestration.content_manager import ContentManager
from comp_synth.schema.content_item import ContentItem


class TopicGroup(TypedDict):
    """主题分组，包含 LLM 总结和历史关联"""

    topic: str
    summary: str
    articles: list[dict]  # {title, summary, url}
    related_historical: list[dict]  # {title, summary, url}


class PipelineState(TypedDict):
    """Plain async pipeline state definition."""

    sources: list[dict]
    raw_items: list[ContentItem]
    new_items: list[ContentItem]
    topic_groups: list[TopicGroup]
    report: str
    publish_results: dict
    notification_results: list[dict]
    errors: list[str]
    content_manager: ContentManager | None

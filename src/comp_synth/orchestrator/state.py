from typing import TypedDict

from comp_synth.schemas.base import ContentItem


class TopicGroup(TypedDict):
    """主题分组，包含 LLM 总结和历史关联"""

    topic: str
    summary: str
    articles: list[dict]  # {title, summary, url}
    related_historical: list[dict]  # {title, summary, url}


class PipelineState(TypedDict):
    """LangGraph 流水线状态定义"""

    sources: list[dict]
    raw_items: list[ContentItem]
    new_items: list[ContentItem]
    topic_groups: list[TopicGroup]
    report: str
    publish_results: dict
    errors: list[str]

import json
import uuid
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel

from comp_synth.config import settings
from comp_synth.llm_provider import registry as _llm_registry
from comp_synth.orchestration.content_manager import ContentManager
from comp_synth.orchestration.state import PipelineState
from comp_synth.prompt import (
    CONTENT_ANALYST_PROMPT,
    REPORT_GENERATOR_PROMPT,
    TOPIC_MERGE_PROMPT,
)
from comp_synth.report_format_checker import ReportFormatChecker
from comp_synth.schema.content_item import ContentItem
from comp_synth.services.source_service import SourceService
from comp_synth.utils.json_extraction import coerce_text_content


class ArticleInTopic(BaseModel):
    """A single article within a topic group."""
    title: str
    summary: str
    url: str


class TopicGroup(BaseModel):
    """A topic group with summary and related articles."""
    topic: str
    summary: str
    articles: list[ArticleInTopic]


class TopicAnalysis(BaseModel):
    """LLM structured output for topic analysis."""
    topics: list[TopicGroup]


async def fetch_sources(state: PipelineState) -> dict:
    """从所有订阅源采集内容（委托给 ContentManager）"""
    source_service = SourceService(
        subscriptions_path=settings.subscriptions_path,
        source_db_path=settings.crawl_db_path,
    )
    source_configs = source_service.list_sources()
    sources = [s.raw_config for s in source_configs if s.enabled]

    if not sources:
        return {
            "sources": [],
            "raw_items": [],
            "errors": ["No enabled sources configured"],
        }

    # Create ContentManager and store in state for later use by deduplicate
    manager = ContentManager()
    run_id = f"pipeline-{uuid.uuid4().hex[:12]}"
    result = await manager.fetch_all(sources, run_id=run_id)

    logger.info(
        f"内容采集完成: {len(result.items)} 条内容, "
        f"{len(result.errors)} 个错误"
    )

    return {
        "sources": sources,
        "raw_items": result.items,
        "source_counts": result.source_counts,
        "content_manager": manager,
        "crawl_run_id": run_id,
        "errors": result.errors,
    }


async def deduplicate(state: PipelineState) -> dict:
    """委托 ContentManager 合并历史内容,过滤已爬取的内容"""
    manager = state.get("content_manager")
    raw_items = state.get("raw_items", [])

    if manager is None:
        logger.warning("ContentManager not in state, skipping historical merge")
        return {"new_items": list(raw_items)}

    new_items = manager.merge_historical_items(raw_items)

    logger.info(f"去重和合并完成: {len(raw_items)} 条原始内容 → {len(new_items)} 条最终内容")
    return {"new_items": new_items}


async def _summarize_chunk(
    llm,
    chunk: list[ContentItem],
    item_map: dict[str, ContentItem],
) -> list[dict] | None:
    """Summarize a single chunk of articles via LLM, returning topic groups or None."""
    articles_text = "\n".join(
        f"---\n文章 {i}:\n标题: {item.title}\nURL: {item.url}\n"
        f"标签: {', '.join(item.tags)}\n摘要: {item.summary}\n---"
        for i, item in enumerate(chunk, 1)
    )

    structured_llm = llm.with_structured_output(TopicAnalysis)
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            result: TopicAnalysis = await structured_llm.ainvoke([
                SystemMessage(content=CONTENT_ANALYST_PROMPT),
                HumanMessage(content=f"以下是 {len(chunk)} 篇文章，请分析：\n{articles_text}"),
            ])
            logger.debug(f"[summarize_chunk] attempt={attempt}/{max_retries} result_type={type(result).__name__} result={result}")
            if result is None:
                logger.warning("[summarize_chunk] attempt={attempt}/{max}: LLM 返回 None", attempt=attempt, max=max_retries)
                continue
            return [
                {
                    "topic": t.topic,
                    "summary": t.summary,
                    "articles": [
                        {
                            "title": a.title,
                            "summary": a.summary,
                            "url": a.url,
                            "tags": item_map.get(a.url, ContentItem(source="", url="")).tags,
                        }
                        for a in t.articles
                    ],
                }
                for t in result.topics
            ]
        except Exception as e:
            logger.warning(
                "[summarize_chunk] attempt={attempt}/{max}: {error}",
                attempt=attempt, max=max_retries, error=e,
            )
    return None


async def _merge_topics(llm, all_topics: list[dict]) -> list[dict]:
    """Merge overlapping topics across chunks via a single LLM call."""
    topics_json = json.dumps(all_topics, ensure_ascii=False, indent=2)
    try:
        structured_llm = llm.with_structured_output(TopicAnalysis)
        result: TopicAnalysis = await structured_llm.ainvoke([
            SystemMessage(content=TOPIC_MERGE_PROMPT),
            HumanMessage(content=f"请合并以下主题分组：\n{topics_json}"),
        ])
        logger.debug(f"[merge_topics] result_type={type(result).__name__} result={result}")
        if result is None:
            raise ValueError("LLM 返回 None")
        return [
            {
                "topic": t.topic,
                "summary": t.summary,
                "articles": [a.model_dump() for a in t.articles],
                "related_historical": [],
            }
            for t in result.topics
        ]
    except Exception as e:
        logger.warning("[merge_topics] 合并失败，直接拼接: {error}", error=e)
        for t in all_topics:
            t["related_historical"] = []
        return all_topics


async def summarize(state: PipelineState) -> dict:
    """使用 LLM 按主题分组并总结内容（支持分片处理）"""
    new_items = state.get("new_items", [])
    if not new_items:
        return {"topic_groups": [], "report": ""}

    llm = _llm_registry.llm_registry.get(settings.model)
    item_map = {item.url: item for item in new_items}
    chunk_size = settings.summarize_chunk_size

    # Single-chunk fast path
    if len(new_items) <= chunk_size:
        topic_groups = await _summarize_chunk(llm, new_items, item_map)
        if topic_groups:
            for t in topic_groups:
                t["related_historical"] = []
            logger.info(f"LLM 分组完成: {len(topic_groups)} 个主题")
            return {"topic_groups": topic_groups}
        # Fallback
        return {"topic_groups": _fallback_groups(new_items)}

    # Multi-chunk path
    all_chunk_topics: list[dict] = []
    for start in range(0, len(new_items), chunk_size):
        chunk = new_items[start:start + chunk_size]
        logger.info(
            "[summarize] 处理分片 {start}-{end}/{total}",
            start=start, end=start + len(chunk), total=len(new_items),
        )
        chunk_topics = await _summarize_chunk(llm, chunk, item_map)
        if chunk_topics:
            all_chunk_topics.extend(chunk_topics)
        else:
            logger.warning("[summarize] 分片 {start}-{end} 处理失败，使用 fallback", start=start, end=start + len(chunk))
            all_chunk_topics.extend(_fallback_groups(chunk))

    # Merge cross-chunk topics
    if len(all_chunk_topics) > 1:
        logger.info("[summarize] 合并 {count} 个主题分组...", count=len(all_chunk_topics))
        topic_groups = await _merge_topics(llm, all_chunk_topics)
    else:
        topic_groups = all_chunk_topics
        for t in topic_groups:
            t.setdefault("related_historical", [])

    logger.info(f"LLM 分组完成: {len(topic_groups)} 个主题")
    return {"topic_groups": topic_groups}


def _fallback_groups(items: list[ContentItem]) -> list[dict]:
    """Build a single fallback topic group from items."""
    return [{
        "topic": "综合",
        "summary": "最近采集的文章汇总。",
        "articles": [
            {"title": item.title, "summary": item.summary or "", "url": item.url, "tags": item.tags}
            for item in items
        ],
        "related_historical": [],
    }]


async def publish(state: PipelineState) -> dict:
    """使用 LLM 生成结构化 Markdown 报告并写入文件"""
    topic_groups = state.get("topic_groups", [])
    if not topic_groups:
        return {"report": "", "publish_results": {"status": "skipped", "reason": "无内容"}}

    llm = _llm_registry.llm_registry.get(settings.model)

    # 构建主题分组文本
    date_str = datetime.now().strftime("%Y-%m-%d")
    groups_text = f"## 日期: {date_str}\n\n"

    for i, group in enumerate(topic_groups, 1):
        groups_text += f"### 主题 {i}: {group['topic']}\n"
        groups_text += f"#### 主题概要: {group['summary']}\n\n"
        groups_text += "#### 文章列表:\n"
        for art in group["articles"]:
            tags_str = ", ".join(art.get("tags", ["其他"]))
            groups_text += f"- title: {art['title']}\n  url: {art['url']}\n  tags: {tags_str}\n  summary: {art.get('summary', '')}\n"

        if group.get("related_historical"):
            groups_text += "\n#### 相关历史内容:\n"
            for rel in group["related_historical"]:
                groups_text += f"- title: {rel['title']}\n  url: {rel['url']}\n  summary: {rel.get('summary', '')}\n"
        groups_text += "\n"

    logger.info(f"正在使用 LLM 生成报告 ({len(topic_groups)} 个主题)...")
    response = await llm.ainvoke([
        SystemMessage(content=REPORT_GENERATOR_PROMPT),
        HumanMessage(content=f"请根据以下主题分组信息生成报告：\n\n{groups_text}"),
    ])

    report = coerce_text_content(response.content)

    # 格式检查（警告但不阻断）
    checker = ReportFormatChecker(report)
    result = checker.check_all()
    if not result["passed"]:
        for err in result["errors"]:
            logger.warning(f"报告格式检查未通过: {err}")
    for warn in result["warnings"]:
        logger.warning(warn)

    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")
    output_path = output_dir / f"digest_{timestamp}.md"
    output_path.write_text(report, encoding="utf-8")

    logger.info(f"报告已写入: {output_path}")
    return {
        "report": report,
        "publish_results": {
            "status": "success",
            "path": str(output_path),
            "format_check": result,
        },
    }

async def notify(state: PipelineState) -> dict:
    """Send report to all configured notification channels."""
    from comp_synth.publishers.registry import get_enabled_publishers

    report: str = state.get("report", "")
    publish_results: dict = state.get("publish_results", {})

    if not report or publish_results.get("status") == "skipped":
        return {"notification_results": []}

    channels: list[str] = settings.get_channels()
    if not channels:
        return {"notification_results": []}

    publishers = get_enabled_publishers(channels)
    results: list[dict] = []
    for pub in publishers:
        try:
            result = await pub.publish(report, pub.get_config())
            result["channel"] = pub.channel_name
            results.append(result)
        except Exception as e:
            logger.error("Notification failed for {}: {}", pub.channel_name, e)
            results.append({"status": "error", "channel": pub.channel_name, "error": str(e)})

    return {"notification_results": results}


def use_last_digest(state: PipelineState) -> dict:
    """Reuse the newest generated digest when there is no new content."""
    output_dir = Path(settings.output_dir)
    digest_files = sorted(output_dir.glob("digest_*.md"), key=lambda path: path.stat().st_mtime)
    if not digest_files:
        return {
            "report": "",
            "publish_results": {"status": "skipped", "reason": "No previous digest found"},
        }

    latest = digest_files[-1]
    report = latest.read_text(encoding="utf-8")
    return {
        "report": report,
        "publish_results": {
            "status": "reused",
            "path": latest,
            "reason": "No new content; reused latest digest",
        },
    }

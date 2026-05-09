import json
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from comp_synth.config import settings
from comp_synth.llm_provider.registry import llm_registry
from comp_synth.orchestration.content_manager import ContentManager
from comp_synth.orchestration.state import PipelineState
from comp_synth.prompt import CONTENT_ANALYST_PROMPT, REPORT_GENERATOR_PROMPT
from comp_synth.report_format_checker import ReportFormatChecker
from comp_synth.schema.content_item import ContentItem
from comp_synth.services.source_service import SourceService
from comp_synth.utils.json_extraction import coerce_text_content, extract_json


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
    result = await manager.fetch_all(sources)

    logger.info(
        f"内容采集完成: {len(result.items)} 条内容, "
        f"{len(result.errors)} 个错误"
    )

    return {
        "sources": sources,
        "raw_items": result.items,
        "source_counts": result.source_counts,
        "content_manager": manager,
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


async def summarize(state: PipelineState) -> dict:
    """使用 LLM 按主题分组并总结内容"""
    new_items = state.get("new_items", [])
    if not new_items:
        return {"topic_groups": [], "report": ""}

    llm = llm_registry.get(settings.model)

    # 构建文章列表
    articles_text = ""
    for i, item in enumerate(new_items, 1):
        tags_str = ", ".join(item.tags)
        articles_text += f"""
---
文章 {i}:
标题: {item.title}
URL: {item.url}
标签: {tags_str}
摘要: {item.summary}
---
"""
    # 构建文章索引映射 (URL -> ContentItem)
    item_map = {item.url: item for item in new_items}

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        logger.info(f"正在使用 LLM 总结 {len(new_items)} 篇文章... (attempt={attempt}/{max_retries})")
        try:
            response = await llm.ainvoke([
                SystemMessage(content=CONTENT_ANALYST_PROMPT),
                HumanMessage(content=f"以下是 {len(new_items)} 篇文章，请分析：\n{articles_text}"),
            ])
            content = coerce_text_content(response.content).strip()
            logger.debug("[summarize] LLM 原始输出 (前500字): {preview}", preview=content[:500])

            json_str = extract_json(content)
            if not json_str:
                raise ValueError("未找到 JSON 内容")
            result = json.loads(json_str)
            topic_groups = [
                {
                    "topic": t["topic"],
                    "summary": t["summary"],
                    "articles": [
                        {
                            "title": a["title"],
                            "summary": a["summary"],
                            "url": a["url"],
                            "tags": item_map.get(a["url"], ContentItem(source="", url="")).tags,
                        }
                        for a in t["articles"]
                    ],
                    "related_historical": [],
                }
                for t in result["topics"]
            ]
            logger.info(f"LLM 分组完成: {len(topic_groups)} 个主题")
            return {"topic_groups": topic_groups}
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("[summarize] attempt={attempt}/{max} 解析失败: {error}", attempt=attempt, max=max_retries, error=e)
            if attempt < max_retries:
                logger.info("[summarize] 重试 LLM 调用...")

    logger.error("[summarize] {max} 次尝试均失败，使用 fallback 分组", max=max_retries)
    topic_groups = [{
        "topic": "综合",
        "summary": "最近采集的文章汇总。",
        "articles": [
            {"title": item.title, "summary": item.summary or "", "url": item.url, "tags": item.tags}
            for item in new_items
        ],
        "related_historical": [],
    }]
    return {"topic_groups": topic_groups}


async def publish(state: PipelineState) -> dict:
    """使用 LLM 生成结构化 Markdown 报告并写入文件"""
    topic_groups = state.get("topic_groups", [])
    if not topic_groups:
        return {"report": "", "publish_results": {"status": "skipped", "reason": "无内容"}}

    llm = llm_registry.get(settings.model)

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

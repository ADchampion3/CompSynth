import json
from datetime import datetime
from pathlib import Path

import yaml
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from comp_synth.config import settings
from comp_synth.crawlers.adaptive_web_crawler import AdaptiveWebCrawler
from comp_synth.crawlers.rss import RSSCrawler
from comp_synth.llm_provider.registry import llm_registry
from comp_synth.orchestration.state import PipelineState
from comp_synth.prompt import CONTENT_ANALYST_PROMPT, REPORT_GENERATOR_PROMPT
from comp_synth.report_format_checker import ReportFormatChecker
from comp_synth.schema.content_item import WebPageItem
from comp_synth.store.crawl_tracker import CrawlTracker
from comp_synth.store.vector_store import VectorStore

CRAWLER_MAP = {
    "rss": RSSCrawler,
    "web": AdaptiveWebCrawler,
}


async def fetch_sources(state: PipelineState) -> dict:
    """从所有订阅源采集内容"""
    subs_path = settings.subscriptions_path
    with open(subs_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    sources = config.get("sources", [])
    all_items = []
    errors = list(state.get("errors", []))

    for source in sources:
        source_type = source["type"]
        crawler_cls = CRAWLER_MAP.get(source_type)
        if not crawler_cls:
            errors.append(f"未知的订阅源类型: {source_type}")
            continue
        try:
            crawler = crawler_cls()
            user_selectors = source.get("selectors", [])
            items = await crawler.fetch(source, user_selectors=user_selectors)
            all_items.extend(items)
            logger.info(f"从 {source.get('name', source['url'])} 获取到 {len(items)} 条内容")
        except Exception as e:
            msg = f"爬取 {source.get('url')} 失败: {e}"
            logger.exception(e)
            errors.append(msg)

    return {"sources": sources, "raw_items": all_items, "errors": errors}


async def deduplicate(state: PipelineState) -> dict:
    """去重，过滤已爬取的内容，并合并今日已存储的历史内容"""
    tracker = CrawlTracker()
    raw_items = state.get("raw_items", [])
    new_items = []
    new_urls = set()

    # 1. 处理本次新爬取的内容
    for item in raw_items:
        new_items.append(item)
        new_urls.add(item.url)

    # 2. 合并今日在本次运行前已存储的历史内容
    # 元数据从 SQLite 获取，内容从 VectorStore 获取
    today_items = tracker.get_today_items("web")
    today_article_ids = [f"web:{item['url']}" for item in today_items if item["url"] not in new_urls]

    if today_article_ids:
        # 从 SQLite 获取元数据
        stored_metadata = {item["article_id"]: item for item in tracker.get_articles_by_ids(today_article_ids)}

        for article_id in today_article_ids:
            url = article_id.split(":", 1)[1] if ":" in article_id else article_id
            if url in new_urls:
                continue

            meta = stored_metadata.get(article_id, {})
            historical_item = WebPageItem(
                source=meta.get("source", "web"),
                url=url,
                title=meta.get("title", ""),
                summary=meta.get("summary", ""),
                collected_at=datetime.fromisoformat(meta.get("crawled_at", datetime.now().isoformat())),
            )
            new_items.append(historical_item)
            new_urls.add(url)
            logger.info(f"合并今日历史内容: {url}")

    logger.info(f"去重完成: {len(raw_items)} 条原始内容 → {len(new_items)} 条最终内容")
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
        articles_text += f"""
---
文章 {i}:
标题: {item.title}
URL: {item.url}
摘要: {item.summary}
---
"""
    logger.info(f"正在使用 LLM 总结 {len(new_items)} 篇文章...")
    response = await llm.ainvoke([
        SystemMessage(content=CONTENT_ANALYST_PROMPT),
        HumanMessage(content=f"以下是 {len(new_items)} 篇文章，请分析：\n{articles_text}"),
    ])

    try:
        content = response.content
        # 处理可能的 markdown 代码块包裹
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content)
        topic_groups = [
            {
                "topic": t["topic"],
                "summary": t["summary"],
                "articles": [
                    {"title": a["title"], "summary": a["summary"], "url": a["url"]}
                    for a in t["articles"]
                ],
                "related_historical": [],
            }
            for t in result["topics"]
        ]
        logger.info(f"LLM 分组完成: {len(topic_groups)} 个主题")
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"LLM 输出解析失败 ({e})，使用 fallback 分组")
        topic_groups = [{
            "topic": "综合",
            "summary": "最近采集的文章汇总。",
            "articles": [
                {"title": item.title, "summary": item.summary or "", "url": item.url}
                for item in new_items
            ],
            "related_historical": [],
        }]

    return {"topic_groups": topic_groups}


async def enrich(state: PipelineState) -> dict:
    """检索历史相关内容，并将新内容存入向量库"""
    tracker = CrawlTracker()
    vs = VectorStore()
    topic_groups = state.get("topic_groups", [])
    new_items = state.get("new_items", [])

    # 当前文章 URL 集合，用于排除
    current_urls = {item.url for item in new_items}

    for group in topic_groups:
        query = f"{group['topic']}: {group['summary']}"
        results = vs.search(query, k=5)
        related = []
        # 获取历史文章的元数据（从 SQLite）
        result_ids = [r["id"] for r in results]
        historical_metadata = {item["article_id"]: item for item in tracker.get_articles_by_ids(result_ids)}

        for r in results:
            article_id = r["id"]
            url = article_id.split(":", 1)[1] if ":" in article_id else article_id
            if url not in current_urls:
                meta = historical_metadata.get(article_id, {})
                related.append({
                    "title": meta.get("title", ""),
                    "summary": r["document"][:200] if r["document"] else "",
                    "url": url,
                })
        group["related_historical"] = related

    # 存入新内容：先保存元数据到 SQLite，再存入向量库
    if new_items:
        vs.add(new_items)
        logger.info(f"已将 {len(new_items)} 条新内容存入向量库和 SQLite")

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
            groups_text += f"- title: {art['title']}\n  url: {art['url']}\n  summary: {art.get('summary', '')}\n"

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

    report = response.content

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

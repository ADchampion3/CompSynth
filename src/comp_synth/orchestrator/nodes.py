import json
from datetime import datetime
from pathlib import Path

import yaml
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from comp_synth.config import settings
from comp_synth.crawler.adaptive_crawler import AdaptiveWebCrawler
from comp_synth.crawler.rss_crawler import RSSCrawler
from comp_synth.llm.registry import LLMRegistry
from comp_synth.orchestrator.state import PipelineState
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
            user_selectors = source.get("selectors", {})
            items = await crawler.fetch(source, user_selectors=user_selectors)
            all_items.extend(items)
            logger.info(f"从 {source.get('name', source['url'])} 获取到 {len(items)} 条内容")
        except Exception as e:
            msg = f"爬取 {source.get('url')} 失败: {e}"
            logger.error(msg)
            errors.append(msg)

    return {"sources": sources, "raw_items": all_items, "errors": errors}


async def deduplicate(state: PipelineState) -> dict:
    """去重，过滤已爬取的内容"""
    tracker = CrawlTracker()
    raw_items = state.get("raw_items", [])
    new_items = []

    for item in raw_items:
        if tracker.is_crawled(item.source, item.url):
            logger.info(f"{item.url}\({item.title}\)已爬取, 已忽略")
            continue
        new_items.append(item)
        metadata = {}
        if hasattr(item, "feed_url"):
            metadata["feed_url"] = item.feed_url
        tracker.mark_crawled(item.source, item.url, metadata=metadata)

    logger.info(f"去重完成: {len(raw_items)} 条原始内容 → {len(new_items)} 条新内容")
    return {"new_items": new_items}


async def summarize(state: PipelineState) -> dict:
    """使用 LLM 按主题分组并总结内容"""
    new_items = state.get("new_items", [])
    if not new_items:
        return {"topic_groups": [], "report": ""}

    llm = LLMRegistry({
        "openai_api_key": settings.openai_api_key,
        "openai_base_url": settings.openai_base_url,
        "model": settings.model,
    }).get(settings.model)

    # 构建文章列表
    articles_text = ""
    for i, item in enumerate(new_items, 1):
        content_preview = item.content[:1500] if item.content else ""
        articles_text += f"""
---
文章 {i}:
标题: {item.title}
URL: {item.url}
摘要: {item.summary}
内容: {content_preview}
---
"""

    system_prompt = """你是一个内容分析师。你将收到一组文章。
你的任务：
1. 将它们按主题/话题分组（创建有意义的主题名称）。
2. 为每个主题写一段简洁的总结（2-3 句话概括关键要点）。
3. 为每个主题下的每篇文章写一句话总结。

以如下 JSON 格式回复：
{
  "topics": [
    {
      "topic": "主题名称",
      "summary": "主题整体总结...",
      "articles": [
        {"index": 1, "title": "...", "summary": "一句话总结", "url": "..."}
      ]
    }
  ]
}

规则：
- 每篇文章必须出现在恰好一个主题中。
- 如果文章之间没有共同主题，每篇单独一个主题。
- 使用原始文章的标题和 URL，不要修改。
- 总结要简洁且有信息量。
- 仅回复 JSON，不要 markdown 代码块。"""

    logger.info(f"正在使用 LLM 总结 {len(new_items)} 篇文章...")
    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
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
    vs = VectorStore()
    topic_groups = state.get("topic_groups", [])
    new_items = state.get("new_items", [])

    # 当前文章 URL 集合，用于排除
    current_urls = {item.url for item in new_items}

    for group in topic_groups:
        query = f"{group['topic']}: {group['summary']}"
        results = vs.search(query, k=5)
        related = []
        for r in results:
            meta = r["metadata"]
            if meta.get("url") not in current_urls:
                related.append({
                    "title": meta.get("title", ""),
                    "summary": r["document"][:200],
                    "url": meta.get("url", ""),
                })
        group["related_historical"] = related

    # 存入新内容供未来检索
    if new_items:
        vs.add(new_items)
        logger.info(f"已将 {len(new_items)} 条新内容存入向量库")

    return {"topic_groups": topic_groups}


async def publish(state: PipelineState) -> dict:
    """生成 Markdown 报告并写入文件"""
    topic_groups = state.get("topic_groups", [])
    if not topic_groups:
        return {"report": "", "publish_results": {"status": "skipped", "reason": "无内容"}}

    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [f"# 内容摘要 - {date_str}\n"]

    for group in topic_groups:
        lines.append(f"## {group['topic']}\n")
        lines.append(f"{group['summary']}\n")

        lines.append("### 文章\n")
        for art in group["articles"]:
            lines.append(f"- **[{art['title']}]({art['url']})**")
            if art.get("summary"):
                lines.append(f"  {art['summary']}\n")

        if group.get("related_historical"):
            lines.append("### 相关历史内容\n")
            for rel in group["related_historical"]:
                lines.append(f"- [{rel['title']}]({rel['url']})")
                if rel.get("summary"):
                    lines.append(f"  {rel['summary']}\n")

        lines.append("---\n")

    report = "\n".join(lines)

    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"digest_{timestamp}.md"
    output_path.write_text(report, encoding="utf-8")

    logger.info(f"报告已写入: {output_path}")
    return {
        "report": report,
        "publish_results": {"status": "success", "path": str(output_path)},
    }

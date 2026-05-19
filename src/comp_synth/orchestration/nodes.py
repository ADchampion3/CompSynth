import uuid
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from comp_synth.config import settings
from comp_synth.llm_provider import registry as _llm_registry
from comp_synth.orchestration.content_manager import ContentManager
from comp_synth.orchestration.state import PipelineState
from comp_synth.prompt import CONTENT_ANALYST_PROMPT, REPORT_GENERATOR_PROMPT
from comp_synth.report_format_checker import ReportFormatChecker
from comp_synth.schema.content_item import ContentItem
from comp_synth.services.source_service import SourceService
from comp_synth.utils.json_extraction import coerce_text_content


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
        "内容采集完成: {items} 条内容, {errors} 个错误",
        items=len(result.items), errors=len(result.errors),
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

    logger.info("去重和合并完成: {raw} 条原始内容 → {new} 条最终内容", raw=len(raw_items), new=len(new_items))
    return {"new_items": new_items}


async def _summarize_chunk(llm, chunk: list[ContentItem]) -> str | None:
    """Summarize a single chunk of articles via LLM, returning markdown or None."""
    articles_text = "\n".join(
        f"---\n文章 {i}:\n标题: {item.title}\nURL: {item.url}\n"
        f"标签: {', '.join(item.tags)}\n摘要: {item.summary}\n---"
        for i, item in enumerate(chunk, 1)
    )

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = await llm.ainvoke([
                SystemMessage(content=CONTENT_ANALYST_PROMPT),
                HumanMessage(content=f"以下是 {len(chunk)} 篇文章，请分析：\n{articles_text}"),
            ])
            text = coerce_text_content(response.content).strip()
            if text:
                return text
            logger.warning("[summarize_chunk] attempt={attempt}/{max}: empty response", attempt=attempt, max=max_retries)
        except Exception as e:
            logger.warning("[summarize_chunk] attempt={attempt}/{max}: {error}", attempt=attempt, max=max_retries, error=e)
    return None


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~1 token per 1.5 Chinese chars or ~4 English chars."""
    return len(text) // 3


async def _format_report(llm, combined_summary: str) -> str:
    """Apply REPORT_GENERATOR_PROMPT to generate one formatted report."""
    try:
        response = await llm.ainvoke([
            SystemMessage(content=REPORT_GENERATOR_PROMPT),
            HumanMessage(
                content=f"以下是今日采集内容的主题分析，请生成格式规范的报告：\n\n{combined_summary}"
            ),
        ])
        text = coerce_text_content(response.content).strip()
        if text:
            return text
        logger.warning("[format_report] empty response, using raw summary")
    except Exception as e:
        logger.warning("[format_report] format failed, using raw summary: {error}", error=e)
    return combined_summary


async def _format_report_grouped(
    llm, chunks_md: list[str], max_tokens_per_group: int = 12000,
) -> list[str]:
    """Split chunk summaries into token-bounded groups, format each group separately."""
    groups: list[str] = []
    current_group: list[str] = []
    current_tokens = 0

    for chunk_md in chunks_md:
        chunk_tokens = _estimate_tokens(chunk_md)
        if current_group and current_tokens + chunk_tokens > max_tokens_per_group:
            groups.append("\n\n".join(current_group))
            current_group = []
            current_tokens = 0
        current_group.append(chunk_md)
        current_tokens += chunk_tokens

    if current_group:
        groups.append("\n\n".join(current_group))

    report_parts: list[str] = []
    for i, group in enumerate(groups):
        logger.info(
            "[summarize] 格式化报告分组 {part}/{total} (~{tokens} tokens)",
            part=i + 1, total=len(groups), tokens=_estimate_tokens(group),
        )
        formatted = await _format_report(llm, group)
        report_parts.append(formatted)

    return report_parts


async def summarize(state: PipelineState) -> dict:
    """使用 LLM 按主题分组并总结内容，格式化为报告（支持分片处理）"""
    new_items = state.get("new_items", [])
    if not new_items:
        return {"report": "", "report_parts": []}

    llm = _llm_registry.llm_registry.get(settings.model)
    chunk_size = settings.summarize_chunk_size

    # Split into chunks and summarize each with CONTENT_ANALYST_PROMPT
    chunks_md: list[str] = []
    for start in range(0, len(new_items), chunk_size):
        chunk = new_items[start:start + chunk_size]
        logger.info(
            "[summarize] 处理分片 {start}-{end}/{total}",
            start=start, end=start + len(chunk), total=len(new_items),
        )
        md = await _summarize_chunk(llm, chunk)
        if md:
            chunks_md.append(md)
        else:
            logger.warning("[summarize] 分片 {start}-{end} 处理失败，使用 fallback", start=start, end=start + len(chunk))
            chunks_md.append(_fallback_report(chunk))

    # Apply REPORT_GENERATOR_PROMPT to generate formatted report(s)
    # Try single report first; split into groups if content too large
    combined_summary = "\n\n".join(chunks_md)
    total_tokens = _estimate_tokens(combined_summary)

    if total_tokens <= 12000:
        logger.info("[summarize] 生成单份格式化报告 (~{tokens} tokens)", tokens=total_tokens)
        report = await _format_report(llm, combined_summary)
        report_parts = [report]
    else:
        report_parts = await _format_report_grouped(llm, chunks_md)

    logger.info("报告生成完成: {parts} 份报告", parts=len(report_parts))
    combined = "\n\n---\n\n".join(report_parts)
    return {"report": combined, "report_parts": report_parts}


def _fallback_report(items: list[ContentItem]) -> str:
    """Build a fallback markdown report when LLM summarization fails."""
    lines = ["## 综合", "### 主题概要", "最近采集的文章汇总。", "", "### 文章列表"]
    for i, item in enumerate(items, 1):
        title = item.title or "无标题"
        url = item.url
        summary = item.summary or "暂无摘要"
        lines.append(f"{i}. **[{title}]({url})** - {summary}")
    return "\n".join(lines)


async def publish(state: PipelineState) -> dict:
    """将 Markdown 报告写入文件"""
    report: str = state.get("report", "")
    report_parts: list[str] = state.get("report_parts", [])
    if not report:
        return {"report": "", "publish_results": {"status": "skipped", "reason": "无内容"}}

    # 格式检查（警告但不阻断）
    checker = ReportFormatChecker(report)
    result = checker.check_all()
    if not result["passed"]:
        for err in result["errors"]:
            logger.warning("报告格式检查未通过: {error}", error=err)
    for warn in result["warnings"]:
        logger.warning(warn)

    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")

    written_files: list[str] = []

    # Write individual part files when there are multiple parts
    if len(report_parts) > 1:
        for i, part in enumerate(report_parts, 1):
            part_path = output_dir / f"digest_{timestamp}_p{i}.md"
            part_path.write_text(part, encoding="utf-8")
            written_files.append(str(part_path))
            logger.info("报告分片已写入: {path}", path=part_path)

    # Write combined digest (main file)
    main_path = output_dir / f"digest_{timestamp}.md"
    main_path.write_text(report, encoding="utf-8")
    written_files.insert(0, str(main_path))
    logger.info("报告已写入: {path}", path=main_path)

    return {
        "report": report,
        "publish_results": {
            "status": "success",
            "path": str(main_path),
            "files": written_files,
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

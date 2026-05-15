"""ContentManager - orchestrates content fetching, deduplication, and persistence."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from urllib.parse import urlparse

from loguru import logger

from comp_synth.crawlers.adaptive_web_crawler import AdaptiveWebCrawler
from comp_synth.crawlers.base import BaseCrawler
from comp_synth.crawlers.dynamic_web_crawler import DynamicWebCrawler
from comp_synth.crawlers.rss import RSSCrawler
from comp_synth.schema.content_item import ContentItem, RSSItem, WebPageItem
from comp_synth.store.crawl_tracker import CrawlTracker
from comp_synth.store.source_outcome_store import SourceOutcomeStore
from comp_synth.utils.json_extraction import coerce_text_content, extract_json
from comp_synth.utils.rate_limiter import DomainRateLimiter

# ============================================================================
# Source Strategy Pattern - 消除硬编码的来源类型
# ============================================================================


class SourceStrategy(Protocol):
    """策略接口: 定义如何获取历史内容和构建 ContentItem."""

    @property
    def source_type(self) -> str:
        """来源类型标识 (e.g., 'rss', 'web')."""
        ...

    def get_today_items(self, tracker: CrawlTracker) -> list[dict]:
        """从 tracker 获取今日该来源的历史内容."""
        ...

    def create_historical_item(self, metadata: dict) -> ContentItem:
        """根据 SQLite 元数据构建 ContentItem 子类."""
        ...


class RSSSourceStrategy:
    """RSS 来源策略."""

    source_type = "rss"

    def get_today_items(self, tracker: CrawlTracker) -> list[dict]:
        return tracker.get_today_items(self.source_type)

    def create_historical_item(self, metadata: dict) -> ContentItem:
        extra = metadata.get("metadata", {})
        tags = extra.get("tags", ["其他"])
        return RSSItem(
            source=metadata.get("source", "rss"),
            url=metadata.get("url", ""),
            title=metadata.get("title", ""),
            summary=metadata.get("summary", ""),
            tags=tags,
            collected_at=datetime.fromisoformat(metadata.get("crawled_at", datetime.now().isoformat())),
            published_at=datetime.fromisoformat(metadata["published_at"])
            if metadata.get("published_at") else None,
        )


class WebSourceStrategy:
    """Web 来源策略."""

    source_type = "web"

    def get_today_items(self, tracker: CrawlTracker) -> list[dict]:
        return tracker.get_today_items(self.source_type)

    def create_historical_item(self, metadata: dict) -> ContentItem:
        extra = metadata.get("metadata", {})
        tags = extra.get("tags", ["其他"])
        return WebPageItem(
            source=metadata.get("source", "web"),
            url=metadata.get("url", ""),
            title=metadata.get("title", ""),
            summary=metadata.get("summary", ""),
            tags=tags,
            collected_at=datetime.fromisoformat(metadata.get("crawled_at", datetime.now().isoformat())),
        )


class JavaScriptSourceStrategy(WebSourceStrategy):
    """JavaScript 来源策略 (复用 WebSourceStrategy)."""

    source_type = "javascript"


class SourceStrategyFactory:
    """工厂: 管理 SourceStrategy 注册与获取."""

    def __init__(self):
        self._strategies: dict[str, SourceStrategy] = {}

    def register(self, strategy: SourceStrategy) -> None:
        """注册来源策略."""
        self._strategies[strategy.source_type] = strategy

    def get_strategy(self, source_type: str) -> SourceStrategy | None:
        """获取指定来源的策略."""
        return self._strategies.get(source_type)

    def get_all_source_types(self) -> list[str]:
        """获取所有已注册来源类型 (非硬编码)."""
        return list(self._strategies.keys())

    @staticmethod
    def create_default_factory() -> "SourceStrategyFactory":
        """创建内置默认策略的工厂."""
        factory = SourceStrategyFactory()
        factory.register(RSSSourceStrategy())
        factory.register(WebSourceStrategy())
        factory.register(JavaScriptSourceStrategy())
        return factory


# ============================================================================
# Protocol Definitions for Crawlers
# ============================================================================


class RSSCrawlerProtocol(Protocol):
    """Protocol for RSS crawler interface."""

    async def fetch_feed(self, source_config: dict) -> list[RSSItem]:
        """Fetch raw RSS items without dedup/persistence."""
        ...

    async def fetch_detail(self, item: RSSItem, site_name: str) -> WebPageItem | RSSItem:
        """Fetch article detail page (always executes)."""
        ...


class WebCrawlerProtocol(Protocol):
    """Protocol for web crawler interface."""

    async def fetch_page(self, url: str, user_selectors: list[dict[str, str]] | None = None) -> list[WebPageItem]:
        """Fetch raw items from a page without dedup/persistence."""
        ...

    async def fetch_detail(self, item: WebPageItem, site_name: str) -> WebPageItem | None:
        """Fetch article detail page (always executes)."""
        ...


@dataclass
class FetchResult:
    """Result of a fetch_all operation."""

    items: list[ContentItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source_counts: dict[str, int] = field(default_factory=dict)


def normalize_selectors(selectors: object) -> list[dict[str, str]] | None:
    if selectors is None:
        return None
    if isinstance(selectors, dict):
        return [selectors]
    if isinstance(selectors, list) and all(isinstance(item, dict) for item in selectors):
        return selectors
    raise ValueError("selectors must be a mapping or a list of mappings")


class ContentManager:
    """
    Orchestrates content fetching from multiple sources.

    Responsibilities:
    1. Crawler selection based on source type
    2. User selector management (passing from subscriptions.yaml)
    3. Deduplication via CrawlTracker
    4. Detail-fetch orchestration (always fetch detail page)
    5. Batch LLM summarization after all sources fetched
    6. Persistence to CrawlTracker after summarization
    7. Cross-source aggregation and error handling
    """

    CRAWLER_MAP: dict[str, type[BaseCrawler]] = {
        "rss": RSSCrawler,
        "web": AdaptiveWebCrawler,
        "javascript": DynamicWebCrawler,
    }

    ITEM_TIMEOUT = 120  # 单条处理总超时（秒）
    MAX_CONCURRENT = 5  # 最大并发数
    CRAWL_DELAY = 1.5  # 同一站点的详情页请求间隔（秒）

    def __init__(
        self,
        crawl_tracker: CrawlTracker | None = None,
        strategy_factory: SourceStrategyFactory | None = None,
        source_outcome_store: SourceOutcomeStore | None = None,
        tag_vocabulary: list[str] | None = None,
    ):
        self._tracker = crawl_tracker or CrawlTracker()
        self._source_outcome_store = source_outcome_store or SourceOutcomeStore()
        self._crawlers: dict[str, BaseCrawler] = {}
        self._strategy_factory = strategy_factory or SourceStrategyFactory.create_default_factory()
        self._tag_vocabulary = tag_vocabulary
        self._domain_limiter = DomainRateLimiter(min_interval=self.CRAWL_DELAY)

    async def _throttled_fetch_detail(
        self, item: ContentItem, crawler: BaseCrawler, source_type: str, site_name: str,
    ) -> ContentItem | None:
        """带请求间隔的详情页抓取。按域名限流，不同域名可并行。"""
        domain = self._detect_site(item.url)
        await self._domain_limiter.acquire(domain)
        return await crawler.fetch_detail(item, site_name)

    def _get_crawler(self, source_type: str) -> BaseCrawler | None:
        """Get or create a crawler instance for the given source type."""
        if source_type not in self.CRAWLER_MAP:
            return None

        if source_type not in self._crawlers:
            self._crawlers[source_type] = self.CRAWLER_MAP[source_type]()

        return self._crawlers[source_type]

    def _detect_site(self, url: str) -> str:
        """Detect site name from URL."""
        return urlparse(url).netloc or "unknown"

    def _source_key(self, source: dict) -> str:
        """Return a stable key for per-source crawl outcome tracking."""
        return source.get("name") or source.get("url", "unknown")

    async def _process_item(
        self,
        item: ContentItem,
        crawler: BaseCrawler,
        source_type: str,
        extra_metadata: dict | None,
        semaphore: asyncio.Semaphore,
        done_count: list[int],
        total: int,
    ) -> ContentItem | None:
        """处理单条内容：去重 + 抓详情。受信号量控制并发，带总超时兜底。"""
        async with semaphore:
            if self._tracker.is_crawled(source_type, item.url):
                done_count[0] += 1
                logger.info(f"[{source_type} {done_count[0]}/{total}] 已爬取, 跳过: {item.url}")
                return None

            done_count[0] += 1
            my_index = done_count[0]
            logger.info(f"[{source_type} {my_index}/{total}] 开始处理: {item.url}")

            result = item
            try:
                result = await asyncio.wait_for(
                    self._do_process_item(item, crawler, source_type, extra_metadata),
                    timeout=self.ITEM_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.error(f"[{source_type} {my_index}/{total}] 处理超时 ({self.ITEM_TIMEOUT}s): {item.url}")
            finally:
                logger.info(f"[{source_type} {my_index}/{total}] 完成: {item.title[:30]}")
            return result

    async def _do_process_item(
        self,
        item: ContentItem,
        crawler: BaseCrawler,
        source_type: str,
        extra_metadata: dict | None,
    ) -> ContentItem:
        """单条内容的核心处理逻辑（仅 fetch_detail，LLM 摘要延迟到批量阶段）。"""
        try:
            detail = await self._throttled_fetch_detail(item, crawler, source_type, self._detect_site(item.url))
            if detail is not None:
                if source_type == "rss" and isinstance(detail, RSSItem):
                    item = detail
                elif source_type != "rss":
                    item = detail
        except Exception as e:
            logger.error(f"[{source_type}] 详情页抓取失败 {item.url}: {e}")
            return item

        if extra_metadata:
            item.metadata.update(extra_metadata)
        return item

    async def _fetch_items_from_source(
        self,
        source: dict,
        crawler: BaseCrawler,
        source_type: str,
    ) -> list[ContentItem]:
        """Fetch raw items, deduplicate, and fetch detail pages for a single source."""
        source_key = self._source_key(source)

        if source_type == "rss":
            raw_items = await crawler.fetch_feed(source)
            extra = {"feed_url": source["url"], "source_key": source_key}
        elif source_type in ("web", "javascript"):
            user_selectors = normalize_selectors(source.get("selectors"))
            if isinstance(crawler, DynamicWebCrawler):
                raw_items = await crawler.fetch(source, user_selectors=user_selectors)
            else:
                raw_items = await crawler.fetch_page(
                    source["url"],
                    user_selectors=user_selectors,
                    source_key=source_key,
                    source_type=source_type,
                )
            extra = {"source_key": source_key}
        else:
            raw_items = await crawler.fetch(source, user_selectors=normalize_selectors(source.get("selectors")))
            extra = None

        total = len(raw_items)
        logger.info(
            f"[{source_type}] 获取到 {total} 条原始条目，开始并发处理 "
            f"(concurrent={self.MAX_CONCURRENT}, delay={self.CRAWL_DELAY}s)"
        )

        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)
        done_count = [0]
        tasks = [
            self._process_item(item, crawler, source_type, extra, semaphore, done_count, total)
            for item in raw_items
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(f"[{source_type}] 条目处理异常 {raw_items[i].url}: {r}")
            elif r is not None:
                processed.append(r)

        logger.info(f"[{source_type}] 处理完成: {len(processed)}/{total} 条有效内容")
        return processed

    async def _summarize_content(self, title: str, content: str) -> tuple[str, list[str]]:
        """用 LLM 从 content 生成 summary 和 tags（单条 fallback）。"""
        import json

        from langchain_core.messages import HumanMessage, SystemMessage

        from comp_synth.config import settings
        from comp_synth.llm_provider.registry import llm_registry
        from comp_synth.prompt import build_summary_prompt

        truncated = content[:3000] if len(content) > 3000 else content
        llm = llm_registry.get(settings.model)
        prompt_text = build_summary_prompt(tags=self._tag_vocabulary)

        max_retries = 3
        last_text = truncated[:200]
        for attempt in range(1, max_retries + 1):
            try:
                response = await llm.ainvoke([
                    SystemMessage(content=prompt_text),
                    HumanMessage(content=f"标题：{title}\n\n内容：{truncated}"),
                ])
                text = coerce_text_content(response.content).strip()
                last_text = text

                json_str = extract_json(text)
                if not json_str:
                    raise ValueError("未找到 JSON")

                result = json.loads(json_str)
                summary = result.get("summary", "").strip()
                raw_tags = result.get("tags", [])
                valid = set(self._tag_vocabulary) if self._tag_vocabulary else None
                tags = [t for t in raw_tags if valid is None or t in valid] or ["其他"]
                return summary, tags
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(
                    "[summarize_content] attempt={attempt}/{max} 解析失败: {error}",
                    attempt=attempt, max=max_retries, error=e,
                )
                if attempt < max_retries:
                    logger.info("[summarize_content] 重试 LLM 调用...")

        logger.error("[summarize_content] {max} 次尝试均失败, 使用原始文本", max=max_retries)
        return last_text[:200], ["其他"]

    async def _batch_summarize_items(self, items: list[ContentItem]) -> list[ContentItem]:
        """Batch LLM summarize items. Falls back to per-item on batch failure."""
        import json

        from langchain_core.messages import HumanMessage, SystemMessage

        from comp_synth.config import settings
        from comp_synth.llm_provider.registry import llm_registry
        from comp_synth.prompt import build_batch_summary_prompt

        items_with_content = [(i, item) for i, item in enumerate(items) if item.content]
        if not items_with_content:
            return items

        batch_size = settings.llm_batch_size
        llm = llm_registry.get(settings.model)

        for batch_start in range(0, len(items_with_content), batch_size):
            batch = items_with_content[batch_start:batch_start + batch_size]
            articles = [{"title": item.title, "content": item.content[:3000]} for _, item in batch]
            prompt_text = build_batch_summary_prompt(articles, tags=self._tag_vocabulary)

            max_retries = 3
            success = False
            for attempt in range(1, max_retries + 1):
                try:
                    response = await llm.ainvoke([
                        SystemMessage(content=prompt_text),
                        HumanMessage(content=f"请分析以上 {len(articles)} 篇文章。"),
                    ])
                    text = coerce_text_content(response.content).strip()
                    json_str = extract_json(text)
                    if not json_str:
                        raise ValueError("未找到 JSON")

                    results = json.loads(json_str)
                    if not isinstance(results, list) or len(results) != len(batch):
                        raise ValueError(f"期望 {len(batch)} 条结果，得到 {len(results) if isinstance(results, list) else '非数组'}")

                    valid_tags = set(self._tag_vocabulary) if self._tag_vocabulary else None
                    for (orig_idx, item), parsed in zip(batch, results):
                        summary = parsed.get("summary", "").strip()
                        raw_tags = parsed.get("tags", [])
                        tags = [t for t in raw_tags if valid_tags is None or t in valid_tags] or ["其他"]
                        items[orig_idx] = self._apply_summary(item, summary, tags)

                    success = True
                    break
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning(
                        "[batch_summarize] batch={start}-{end} attempt={attempt}/{max}: {error}",
                        start=batch_start, end=batch_start + len(batch),
                        attempt=attempt, max=max_retries, error=e,
                    )

            if not success:
                logger.warning("[batch_summarize] 批量摘要失败，回退到逐条处理")
                for orig_idx, item in batch:
                    try:
                        summary, tags = await self._summarize_content(item.title, item.content)
                        items[orig_idx] = self._apply_summary(item, summary, tags)
                    except Exception as e:
                        logger.warning(f"[batch_summarize] 逐条 fallback 也失败 {item.url}: {e}")

        return items

    def _apply_summary(self, item: ContentItem, summary: str, tags: list[str]) -> ContentItem:
        """Return a new ContentItem with summary and tags applied."""
        if isinstance(item, RSSItem):
            return RSSItem(
                url=item.url,
                title=item.title,
                summary=summary,
                content=item.content,
                tags=tags,
                published_at=item.published_at,
                collected_at=item.collected_at,
                metadata=item.metadata,
            )
        return WebPageItem(
            url=item.url,
            title=item.title,
            summary=summary,
            content=item.content,
            tags=tags,
            collected_at=item.collected_at,
            metadata=item.metadata,
        )

    async def _fetch_single_source(
        self,
        source: dict,
    ) -> tuple[str, list[ContentItem] | None, str | None]:
        """Fetch from a single source. Returns (source_name, items or None, error or None)."""
        source_type = source["type"]
        source_name = source.get("name", source.get("url", "unknown"))

        crawler = self._get_crawler(source_type)
        if not crawler:
            return (source_name, None, f"未知的订阅源类型: {source_type}")

        logger.info(
            "[ContentManager] 开始抓取 {name} (type={type}, url={url})",
            name=source_name, type=source_type, url=source.get("url", ""),
        )

        try:
            items = await self._fetch_items_from_source(source, crawler, source_type)
            logger.info(f"[ContentManager] 从 {source_name} 获取到 {len(items)} 条内容")
            return (source_name, items, None)
        except Exception as e:
            error_msg = f"爬取失败: {e}"
            logger.exception(f"ContentManager: {error_msg}")
            return (source_name, None, error_msg)

    async def fetch_all(
        self,
        sources: list[dict],
    ) -> FetchResult:
        """
        Fetch content from all sources with bounded concurrency,
        then batch-summarize all collected items, then persist.

        Args:
            sources: List of source configs from subscriptions.yaml

        Returns:
            FetchResult with items, errors, and source counts
        """
        if not sources:
            return FetchResult()

        from comp_synth.config import settings

        source_semaphore = asyncio.Semaphore(settings.max_concurrent_sources)

        async def _bounded_fetch(source):
            async with source_semaphore:
                return await self._fetch_single_source(source)

        # Run sources with bounded concurrency
        tasks = [_bounded_fetch(source) for source in sources]
        results = await asyncio.gather(*tasks)

        # Aggregate results — items have detail content but no summary yet
        result = FetchResult()
        for source_name, items, error in results:
            if error:
                result.errors.append(f"[{source_name}] {error}")
                result.source_counts[source_name] = 0
            else:
                result.items.extend(items)
                result.source_counts[source_name] = len(items)

        for source, (source_name, items, error) in zip(sources, results, strict=False):
            count = 0 if error or items is None else len(items)
            self._source_outcome_store.record_source_outcome(source, count, error)

        # Batch LLM summarize all collected items
        if result.items:
            logger.info(f"[ContentManager] 开始批量摘要: {len(result.items)} 条内容")
            result.items = await self._batch_summarize_items(result.items)
            self._tracker.save_articles(result.items)
            logger.info(f"[ContentManager] 批量摘要并持久化完成: {len(result.items)} 条")

        return result

    def get_today_items(self) -> list[dict]:
        """获取今日从所有来源已存储的历史内容 (由策略工厂驱动,无硬编码)."""
        all_items = []
        for source_type in self._strategy_factory.get_all_source_types():
            strategy = self._strategy_factory.get_strategy(source_type)
            if strategy:
                items = strategy.get_today_items(self._tracker)
                all_items.extend(items)
        return all_items

    def merge_historical_items(
        self,
        current_items: list[ContentItem],
    ) -> list[ContentItem]:
        """合并今日历史内容到当前内容列表,去重后返回."""
        new_urls = {item.url for item in current_items}
        today_items = self.get_today_items()
        today_article_ids = [
            f"{item['source']}:{item['url']}"
            for item in today_items
            if item["url"] not in new_urls
        ]

        if not today_article_ids:
            return current_items

        stored_metadata = {
            item["article_id"]: item
            for item in self._tracker.get_articles_by_ids(today_article_ids)
        }

        merged = list(current_items)
        for article_id in today_article_ids:
            url = article_id.split(":", 1)[1] if ":" in article_id else article_id
            if url in new_urls:
                continue

            meta = stored_metadata.get(article_id, {})
            source_type = meta.get("source", "web")
            strategy = self._strategy_factory.get_strategy(source_type)

            if strategy:
                historical_item = strategy.create_historical_item(meta)
                merged.append(historical_item)
                new_urls.add(url)
                logger.info(f"合并今日历史内容: {url} (来源: {source_type})")
            else:
                logger.warning(f"未找到来源策略: {source_type}, 跳过 {url}")

        return merged

    def is_already_crawled(self, source: str, url: str) -> bool:
        """Check if a URL has already been crawled (exposed for testing)."""
        return self._tracker.is_crawled(source, url)

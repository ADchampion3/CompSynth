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
from comp_synth.store.vector_store import VectorStore

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
    4. Detail-fetch orchestration (always fetch detail page + LLM summarize)
    5. Persistence to CrawlTracker after all items collected
    6. Cross-source aggregation and error handling
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
        vector_store: VectorStore | None = None,
    ):
        """
        Initialize ContentManager.

        Args:
            crawl_tracker: Optional CrawlTracker instance. If not provided,
                          a new one will be created. Exposed for testing.
            strategy_factory: Optional strategy factory. If not provided,
                            a default factory with RSS, Web, JavaScript strategies
                            will be created.
            vector_store: Optional VectorStore instance. If not provided,
                         a new one will be created.
        """
        self._tracker = crawl_tracker or CrawlTracker()
        self._vector_store = vector_store or VectorStore()
        self._crawlers: dict[str, BaseCrawler] = {}
        self._strategy_factory = strategy_factory or SourceStrategyFactory.create_default_factory()
        self._last_crawl_time: float = 0.0
        self._crawl_lock = asyncio.Lock()

    async def _throttled_fetch_detail(
        self, item: ContentItem, crawler: BaseCrawler, source_type: str, site_name: str,
    ) -> ContentItem | None:
        """带请求间隔的详情页抓取。确保请求之间至少间隔 CRAWL_DELAY 秒。"""
        async with self._crawl_lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_crawl_time
            if elapsed < self.CRAWL_DELAY:
                await asyncio.sleep(self.CRAWL_DELAY - elapsed)
            self._last_crawl_time = asyncio.get_event_loop().time()

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

    async def _summarize_content(self, title: str, content: str) -> tuple[str, list[str]]:
        """用 LLM 从 readability 提取的 content 生成 summary 和 tags"""
        import json

        from langchain_core.messages import HumanMessage, SystemMessage

        from comp_synth.config import settings
        from comp_synth.llm_provider.registry import llm_registry
        from comp_synth.prompt import ARTICLE_SUMMARY_PROMPT
        from comp_synth.schema.content_item import ALL_TAGS

        truncated = content[:3000] if len(content) > 3000 else content
        llm = llm_registry.get(settings.model)
        response = await llm.ainvoke([
            SystemMessage(content=ARTICLE_SUMMARY_PROMPT),
            HumanMessage(content=f"标题：{title}\n\n内容：{truncated}"),
        ])
        text = response.content.strip()
        try:
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            result = json.loads(text)
            summary = result.get("summary", "").strip()
            raw_tags = result.get("tags", [])
            tags = [t for t in raw_tags if t in ALL_TAGS] or ["其他"]
            return summary, tags
        except (json.JSONDecodeError, KeyError):
            return text, ["其他"]

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
        """处理单条内容：去重、抓详情、LLM 摘要。受信号量控制并发，带总超时兜底。"""
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
        """单条内容的核心处理逻辑（fetch_detail + summarize）。"""
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

        if item.content:
            try:
                summary, tags = await self._summarize_content(item.title, item.content)
                if summary:
                    if source_type == "rss":
                        item = RSSItem(
                            url=item.url,
                            title=item.title,
                            summary=summary,
                            content=item.content,
                            tags=tags,
                            published_at=item.published_at,
                            collected_at=item.collected_at,
                            metadata=item.metadata,
                        )
                    else:
                        item = WebPageItem(
                            url=item.url,
                            title=item.title,
                            summary=summary,
                            content=item.content,
                            tags=tags,
                            collected_at=item.collected_at,
                            metadata=item.metadata,
                        )
            except Exception as e:
                logger.warning(f"[{source_type}] LLM 总结失败 {item.url}: {e}")

        if extra_metadata:
            item.metadata.update(extra_metadata)
        return item

    async def _fetch_rss_source(
        self,
        source: dict,
        crawler: RSSCrawler,
    ) -> list[ContentItem]:
        """Fetch items from an RSS source with dedup, detail-fetch, LLM summarization, and persistence."""
        feed_url = source["url"]
        raw_items = await crawler.fetch_feed(source)
        total = len(raw_items)
        logger.info(f"[RSS] 获取到 {total} 条原始条目，开始并发处理 (concurrent={self.MAX_CONCURRENT}, delay={self.CRAWL_DELAY}s)")

        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)
        done_count = [0]
        tasks = [
            self._process_item(item, crawler, "rss", {"feed_url": feed_url}, semaphore, done_count, total)
            for item in raw_items
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(f"[RSS] 条目处理异常 {raw_items[i].url}: {r}")
            elif r is not None:
                processed.append(r)

        if processed:
            self._tracker.save_articles(processed)
        logger.info(f"[RSS] 处理完成: {len(processed)}/{total} 条有效内容")
        return processed

    async def _fetch_web_source(
        self,
        source: dict,
        crawler: AdaptiveWebCrawler,
    ) -> list[ContentItem]:
        """Fetch items from a web source with dedup, detail-fetch, LLM summarization, and persistence."""
        url = source["url"]
        user_selectors = normalize_selectors(source.get("selectors"))

        if isinstance(crawler, DynamicWebCrawler):
            raw_items = await crawler.fetch(source, user_selectors=user_selectors)
        else:
            raw_items = await crawler.fetch_page(url, user_selectors=user_selectors)
        total = len(raw_items)
        logger.info(f"[Web] 获取到 {total} 条原始条目，开始并发处理 (concurrent={self.MAX_CONCURRENT}, delay={self.CRAWL_DELAY}s)")

        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)
        done_count = [0]
        tasks = [
            self._process_item(item, crawler, "web", None, semaphore, done_count, total)
            for item in raw_items
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(f"[Web] 条目处理异常 {raw_items[i].url}: {r}")
            elif r is not None:
                processed.append(r)

        if processed:
            self._tracker.save_articles(processed)
        logger.info(f"[Web] 处理完成: {len(processed)}/{total} 条有效内容")
        return processed

    async def _fetch_single_source(
        self,
        source: dict,
    ) -> tuple[str, list[ContentItem] | None, str | None]:
        """
        Fetch from a single source. Returns (source_name, items or None, error or None).
        """
        source_type = source["type"]
        source_name = source.get("name", source.get("url", "unknown"))

        crawler = self._get_crawler(source_type)
        if not crawler:
            return (source_name, None, f"未知的订阅源类型: {source_type}")

        try:
            if source_type == "rss":
                items = await self._fetch_rss_source(source, crawler)
            elif source_type == "web":
                items = await self._fetch_web_source(source, crawler)
            elif source_type == "javascript":
                user_selectors = normalize_selectors(source.get("selectors"))
                raw_items = await crawler.fetch(source, user_selectors=user_selectors)
                total = len(raw_items)
                semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)
                done_count = [0]
                results = await asyncio.gather(*[
                    self._process_item(item, crawler, "javascript", None, semaphore, done_count, total)
                    for item in raw_items
                ], return_exceptions=True)
                items = [item for item in results if not isinstance(item, Exception) and item is not None]
                if items:
                    self._tracker.save_articles(items)
            else:
                items = await crawler.fetch(source, user_selectors=normalize_selectors(source.get("selectors")))

            logger.info(
                f"[ContentManager] 从 {source_name} 获取到 {len(items)} 条内容"
            )
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
        Fetch content from all sources concurrently.

        Args:
            sources: List of source configs from subscriptions.yaml

        Returns:
            FetchResult with items, errors, and source counts
        """
        if not sources:
            return FetchResult()

        # Run all sources concurrently
        tasks = [self._fetch_single_source(source) for source in sources]
        results = await asyncio.gather(*tasks)

        # Aggregate results
        result = FetchResult()
        for source_name, items, error in results:
            if error:
                result.errors.append(f"[{source_name}] {error}")
                result.source_counts[source_name] = 0
            else:
                result.items.extend(items)
                result.source_counts[source_name] = len(items)

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

    def enrich(
        self,
        topic_groups: list[dict],
        new_items: list[ContentItem],
    ) -> list[dict]:
        """
        检索历史相关内容,并将新内容存入向量库.

        Args:
            topic_groups: 主题分组列表,每个分组包含 topic, summary, articles
            new_items: 本次新采集的内容列表

        Returns:
            更新后的 topic_groups (每个分组包含 related_historical)
        """
        # 当前文章 URL 集合,用于排除
        current_urls = {item.url for item in new_items}

        for group in topic_groups:
            query = f"{group['topic']}: {group['summary']}"
            results = self._vector_store.search(query, k=5)
            related = []

            # 获取历史文章的元数据 (从 SQLite)
            result_ids = [r["id"] for r in results]
            historical_metadata = {
                item["article_id"]: item
                for item in self._tracker.get_articles_by_ids(result_ids)
            }

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

        # 存入新内容: 先保存元数据到 SQLite,再存入向量库
        if new_items:
            self._vector_store.add(new_items)
            logger.info(f"已将 {len(new_items)} 条新内容存入向量库和 SQLite")

        return topic_groups

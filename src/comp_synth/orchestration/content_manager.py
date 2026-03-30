"""ContentManager - orchestrates content fetching, deduplication, and persistence."""

import asyncio
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlparse

from loguru import logger

from comp_synth.crawlers.adaptive_web_crawler import AdaptiveWebCrawler
from comp_synth.crawlers.base import BaseCrawler
from comp_synth.crawlers.dynamic_web_crawler import DynamicWebCrawler
from comp_synth.crawlers.rss import RSSCrawler
from comp_synth.schema.content_item import ContentItem, RSSItem, WebPageItem
from comp_synth.store.crawl_tracker import CrawlTracker


class RSSCrawlerProtocol(Protocol):
    """Protocol for RSS crawler interface."""

    async def fetch_feed(self, source_config: dict) -> list[RSSItem]:
        """Fetch raw RSS items without dedup/persistence."""
        ...

    async def maybe_fetch_detail(self, item: RSSItem, site_name: str) -> WebPageItem | RSSItem:
        """Fetch detail page if summary is insufficient."""
        ...


class WebCrawlerProtocol(Protocol):
    """Protocol for web crawler interface."""

    async def fetch_page(self, url: str, user_selectors: list[dict[str, str]] | None = None) -> list[WebPageItem]:
        """Fetch raw items from a page without dedup/persistence."""
        ...

    async def maybe_fetch_detail(self, item: WebPageItem, site_name: str) -> WebPageItem | None:
        """Fetch detail page if summary is insufficient."""
        ...


@dataclass
class FetchResult:
    """Result of a fetch_all operation."""

    items: list[ContentItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source_counts: dict[str, int] = field(default_factory=dict)


class ContentManager:
    """
    Orchestrates content fetching from multiple sources.

    Responsibilities:
    1. Crawler selection based on source type
    2. User selector management (passing from subscriptions.yaml)
    3. Deduplication via CrawlTracker
    4. Detail-fetch orchestration (calls maybe_fetch_detail when summary insufficient)
    5. Persistence to CrawlTracker after all items collected
    6. Cross-source aggregation and error handling
    """

    CRAWLER_MAP: dict[str, type[BaseCrawler]] = {
        "rss": RSSCrawler,
        "web": AdaptiveWebCrawler,
        "javascript": DynamicWebCrawler,
    }

    def __init__(self, crawl_tracker: CrawlTracker | None = None):
        """
        Initialize ContentManager.

        Args:
            crawl_tracker: Optional CrawlTracker instance. If not provided,
                          a new one will be created. Exposed for testing.
        """
        self._tracker = crawl_tracker or CrawlTracker()
        self._crawlers: dict[str, BaseCrawler] = {}

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

    async def _fetch_rss_source(
        self,
        source: dict,
        crawler: RSSCrawler,
    ) -> list[ContentItem]:
        """Fetch items from an RSS source with dedup, detail-fetch, and persistence."""
        feed_url = source["url"]
        raw_items = await crawler.fetch_feed(source)

        processed: list[ContentItem] = []
        for item in raw_items:
            # Deduplication check
            if self._tracker.is_crawled("rss", item.url):
                logger.info(f"[ContentManager] RSS: {item.url} 已爬取, 跳过")
                continue

            site_name = self._detect_site(item.url)

            # Detail-fetch if summary insufficient
            if not crawler._is_summary_enough(item.summary):
                item = await crawler.maybe_fetch_detail(item, site_name)

            processed.append(item)

        # Persist all processed items
        if processed:
            for item in processed:
                item.metadata["feed_url"] = feed_url
            self._tracker.save_articles(processed)

        return processed

    async def _fetch_web_source(
        self,
        source: dict,
        crawler: AdaptiveWebCrawler,
    ) -> list[ContentItem]:
        """Fetch items from a web source with dedup, detail-fetch, and persistence."""
        url = source["url"]
        user_selectors = source.get("selectors")

        raw_items = await crawler.fetch_page(url, user_selectors=user_selectors)

        processed: list[ContentItem] = []
        for item in raw_items:
            # Deduplication check
            if self._tracker.is_crawled("web", item.url):
                logger.info(f"[ContentManager] Web: {item.url} 已爬取, 跳过")
                continue

            site_name = self._detect_site(item.url)

            # Detail-fetch if summary insufficient
            if not crawler._is_summary_enough(item.summary):
                enriched = await crawler.maybe_fetch_detail(item, site_name)
                if enriched is not None:
                    item = enriched

            processed.append(item)

        # Persist all processed items
        if processed:
            self._tracker.save_articles(processed)

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
            elif source_type in ("web", "javascript"):
                items = await self._fetch_web_source(source, crawler)
            else:
                items = await crawler.fetch(source, user_selectors=source.get("selectors"))

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

    def is_already_crawled(self, source: str, url: str) -> bool:
        """Check if a URL has already been crawled (exposed for testing)."""
        return self._tracker.is_crawled(source, url)

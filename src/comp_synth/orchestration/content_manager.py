"""ContentManager - orchestrates content fetching from multiple sources."""

from dataclasses import dataclass, field
from typing import Protocol

from loguru import logger

from comp_synth.crawlers.adaptive_web_crawler import AdaptiveWebCrawler
from comp_synth.crawlers.base import BaseCrawler
from comp_synth.crawlers.rss import RSSCrawler
from comp_synth.schema.content_item import ContentItem
from comp_synth.store.crawl_tracker import CrawlTracker


class CrawlerProtocol(Protocol):
    """Protocol defining the crawler interface expected by ContentManager."""

    async def fetch(
        self,
        source_config: dict,
        user_selectors: list[dict[str, str]] | None = None,
    ) -> list[ContentItem]:
        """Fetch content from a single source."""
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
    3. Cross-source aggregation
    4. Error handling per source
    5. Optional: dedup bridging at orchestration level

    Does NOT own persistence - crawlers handle their own save via CrawlTracker.
    """

    CRAWLER_MAP: dict[str, type[BaseCrawler]] = {
        "rss": RSSCrawler,
        "web": AdaptiveWebCrawler,
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

    async def fetch_all(
        self,
        sources: list[dict],
        skip_already_crawled: bool = False,
    ) -> FetchResult:
        """
        Fetch content from all sources.

        Args:
            sources: List of source configs from subscriptions.yaml
            skip_already_crawled: If True, skip URLs already in CrawlTracker
                                  (adds dedup at orchestration level)

        Returns:
            FetchResult with items, errors, and source counts
        """
        result = FetchResult()

        for source in sources:
            source_type = source["type"]
            source_name = source.get("name", source.get("url", "unknown"))

            crawler = self._get_crawler(source_type)
            if not crawler:
                error_msg = f"未知的订阅源类型: {source_type}"
                result.errors.append(f"[{source_name}] {error_msg}")
                result.source_counts[source_name] = 0
                continue

            try:
                user_selectors = source.get("selectors")
                items = await crawler.fetch(
                    source,
                    user_selectors=user_selectors,
                )

                # Optional dedup at orchestration level
                if skip_already_crawled:
                    original_count = len(items)
                    items = self._filter_already_crawled(items, source_type)
                    skipped = original_count - len(items)
                    if skipped > 0:
                        logger.info(
                            f"[ContentManager] 跳过 {skipped} 条已爬取内容: {source_name}"
                        )

                result.items.extend(items)
                result.source_counts[source_name] = len(items)

                logger.info(
                    f"[ContentManager] 从 {source_name} 获取到 {len(items)} 条内容"
                )

            except Exception as e:
                error_msg = f"爬取失败: {e}"
                result.errors.append(f"[{source_name}] {error_msg}")
                result.source_counts[source_name] = 0
                logger.exception(f"ContentManager: {error_msg}")

        return result

    def _filter_already_crawled(
        self,
        items: list[ContentItem],
        source_type: str,
    ) -> list[ContentItem]:
        """Filter out items that have already been crawled."""
        result = []
        for item in items:
            if not self._tracker.is_crawled(source_type, item.url):
                result.append(item)
        return result

    def is_already_crawled(self, source: str, url: str) -> bool:
        """Check if a URL has already been crawled (exposed for testing)."""
        return self._tracker.is_crawled(source, url)

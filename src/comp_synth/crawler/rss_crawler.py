from datetime import datetime, timedelta

import feedparser
from bs4 import BeautifulSoup

from comp_synth.config import settings
from comp_synth.crawler.base import BaseCrawler
from comp_synth.schemas.rss import RSSItem
from comp_synth.store.crawl_tracker import CrawlTracker


class RSSCrawler(BaseCrawler):
    """RSS/Atom 订阅源爬虫"""

    @staticmethod
    def _extract_text(entry) -> str:
        """根据 content-type 提取纯文本，HTML 内容自动去标签"""
        if entry.get("content"):
            block = entry["content"][0]
            raw = block.get("value", "")
            content_type = block.get("type", "text/plain")
            if "html" in content_type:
                return BeautifulSoup(raw, "html.parser").get_text(
                    separator="\n", strip=True
                )
            return raw

        summary = entry.get("summary", "")
        if summary and "<" in summary:
            return BeautifulSoup(summary, "html.parser").get_text(
                separator="\n", strip=True
            )
        return summary

    async def fetch(self, source_config: dict) -> list[RSSItem]:
        feed_url = source_config["url"]
        feed = feedparser.parse(feed_url)

        tracker = CrawlTracker()
        last_crawl = tracker.get_last_crawl_time("rss", feed_url)
        cutoff = (
            last_crawl - timedelta(days=settings.rss_lookback_days)
            if last_crawl
            else None
        )

        items = []
        for entry in feed.entries:
            published_at = None
            if hasattr(entry, "published") and entry.published:
                published_at = datetime(*entry.published_parsed[:6])

            if cutoff and published_at and published_at < cutoff:
                continue

            item = RSSItem(
                url=entry.get("link", ""),
                title=entry.get("title", ""),
                content=self._extract_text(entry),
                summary=entry.get("summary", ""),
                published_at=published_at,
                feed_url=feed_url,
            )
            items.append(item)

        return items

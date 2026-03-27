from datetime import datetime
from urllib.parse import urljoin

import feedparser
from bs4 import BeautifulSoup
from loguru import logger

from comp_synth.crawlers.base import BaseCrawler
from comp_synth.schema.content_item import RSSItem
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

    async def fetch(self, source_config: dict, user_selectors: dict = None) -> list[RSSItem]:
        feed_url = source_config["url"]
        feed = feedparser.parse(feed_url)

        tracker = CrawlTracker()

        items = []
        for entry in feed.entries:
            published_at = None
            if hasattr(entry, "published") and entry.published:
                published_at = datetime(*entry.published_parsed[:6])

            if entry.get("link") == "":
                continue

            url = entry.get("link")
            url = urljoin(source_config["url"], url)

            # URL 去重检查
            if tracker.is_crawled("rss", url):
                logger.info(f"RSS: {url} 已爬取, 跳过")
                continue

            item = RSSItem(
                url=url,
                title=entry.get("title", ""),
                summary=entry.get("summary", ""),
                published_at=published_at,
            )
            items.append(item)

        # 批量保存（避免同一批次内重复已在上面通过 is_crawled 检查保证）
        if items:
            tracker.save_articles([
                {
                    "article_id": item.id,
                    "title": item.title,
                    "summary": item.summary,
                    "published_at": item.published_at.isoformat() if item.published_at else None,
                    "metadata": {"feed_url": feed_url},
                }
                for item in items
            ])

        return items

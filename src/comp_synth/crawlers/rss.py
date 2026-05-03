from datetime import datetime, timedelta
from urllib.parse import urljoin

import feedparser
from bs4 import BeautifulSoup
from loguru import logger
from readability import Document

from comp_synth.crawlers.base import BaseCrawler
from comp_synth.schema.content_item import RSSItem, WebPageItem


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

    async def fetch_detail(self, item: RSSItem, site_name: str) -> WebPageItem | RSSItem:
        """爬取详情页，用 readability 提取内容（始终执行）"""
        logger.debug("[RSS] 抓取详情页 {url}", url=item.url)
        try:
            html = await self._fetch_html(item.url)
            doc = Document(html)
            summary = doc.summary() or ""
            soup = BeautifulSoup(summary, "html.parser")
            summary_text = soup.get_text(separator="\n", strip=True)
            content_html = doc.content() or ""
            content_text = (
                BeautifulSoup(content_html, "html.parser").get_text(separator="\n", strip=True)
                if content_html else ""
            )
            if not summary_text and content_text:
                summary_text = content_text
            return RSSItem(
                url=item.url,
                title=doc.short_title() or item.title,
                summary=summary_text,
                content=content_text,
                metadata={**item.metadata, "site_name": site_name},
            )
        except Exception as e:
            logger.warning(f"详情页爬取失败 {item.url}: {e}")
            return item

    def _filter_feed_items(self, items: list[RSSItem]) -> list[RSSItem]:
        """
        对 RSS 条目进行阈值过滤。

        策略（先时间后数量）：
        1. 有 published_at 的 item → 时间阈值过滤
        2. 无 published_at 的 item → 数量阈值截断
        3. 合并两组结果返回
        """
        from comp_synth.config import settings

        time_threshold_days = settings.list_page_time_threshold_days
        count_threshold = settings.list_page_count_threshold

        items_with_time = []
        items_without_time = []

        for item in items:
            if item.published_at is not None:
                items_with_time.append(item)
            else:
                items_without_time.append(item)

        # ① 有时间的：时间阈值过滤
        if time_threshold_days > 0:
            cutoff = datetime.now() - timedelta(days=time_threshold_days)
            items_with_time = [
                item for item in items_with_time
                if item.published_at and item.published_at >= cutoff
            ]

        # ② 无时间的：数量阈值截断
        if count_threshold > 0:
            items_without_time = items_without_time[:count_threshold]

        return items_with_time + items_without_time

    async def fetch_feed(self, source_config: dict) -> list[RSSItem]:
        """抓取 RSS 源，返回原始条目列表（不含去重和持久化，由 ContentManager 处理）"""
        feed_url = source_config["url"]
        logger.info("[RSS] 开始抓取 feed: {url}", url=feed_url)
        feed = feedparser.parse(feed_url)

        items = []
        for entry in feed.entries:
            published_at = None
            if hasattr(entry, "published") and entry.published:
                published_at = datetime(*entry.published_parsed[:6])

            if entry.get("link") == "":
                continue

            url = entry.get("link")
            url = urljoin(source_config["url"], url)

            item = RSSItem(
                url=url,
                title=entry.get("title", ""),
                summary=entry.get("summary", ""),
                published_at=published_at,
            )
            items.append(item)

        # 阈值过滤
        if items:
            items = self._filter_feed_items(items)
            logger.info("[fetch_feed] 阈值过滤后剩余 {count} 条", count=len(items))

        return items

    async def fetch(self, source_config: dict, user_selectors: list[dict[str, str]] | None = None) -> list[RSSItem]:
        """兼容接口，内部委托给 fetch_feed"""
        return await self.fetch_feed(source_config)

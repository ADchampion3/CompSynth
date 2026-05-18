import time
from abc import ABC, abstractmethod

from loguru import logger

from comp_synth.config import settings
from comp_synth.crawlers.crawlee_fetch import CrawleeFetchService
from comp_synth.schema.content_item import ContentItem


class BaseCrawler(ABC):
    """爬虫基类，定义统一的采集接口"""

    async def _fetch_html(self, url: str) -> str:
        """获取网页 HTML（通过 Crawlee 内置重试机制）"""
        logger.debug("HTTP GET {url} (timeout={timeout}s)", url=url, timeout=settings.request_timeout)
        start = time.monotonic()
        html = await CrawleeFetchService.instance().fetch_html(url)
        elapsed = time.monotonic() - start
        logger.debug("HTTP GET {url} → OK ({elapsed:.1f}s, {size} bytes)", url=url, elapsed=elapsed, size=len(html))
        return html

    def _is_summary_enough(self, summary: str) -> bool:
        """判断 summary 是否足够（不为空且长度 > 100）"""
        return bool(summary and len(summary) > 100)

    async def _fetch_html_with_browser(self, url: str, wait_time: float = 2.0) -> str:
        """使用 Playwright (via Crawlee) 获取渲染后的 HTML（支持动态网站）"""
        logger.debug("Browser GET {url} (wait={wait}s)", url=url, wait=wait_time)
        start = time.monotonic()
        html = await CrawleeFetchService.instance().fetch_html_with_browser(url, wait_time)
        elapsed = time.monotonic() - start
        logger.debug("Browser GET {url} → {size} bytes ({elapsed:.1f}s)", url=url, size=len(html), elapsed=elapsed)
        return html

    @abstractmethod
    async def fetch(self, source_config: dict, user_selectors: list[dict[str, str]] | None = None) -> list[ContentItem]:
        """
        从指定源采集内容

        Args:
            source_config: 源配置，包含url、时间范围等参数
            user_selectors: 用户自定义的选择器列表

        Returns:
            采集到的内容项列表
        """

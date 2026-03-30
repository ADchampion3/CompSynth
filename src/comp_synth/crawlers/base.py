from abc import ABC, abstractmethod

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from comp_synth.config import settings
from comp_synth.schema.content_item import ContentItem


class BaseCrawler(ABC):
    """爬虫基类，定义统一的采集接口"""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        reraise=True,
    )
    async def _fetch_html(self, url: str) -> str:
        """获取网页 HTML（带重试机制）"""
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def _is_summary_enough(self, summary: str) -> bool:
        """判断 summary 是否足够（不为空且长度 > 100）"""
        return bool(summary and len(summary) > 100)

    async def _fetch_html_with_browser(self, url: str, wait_time: float = 2.0) -> str:
        """
        使用 DrissionPage 获取渲染后的 HTML（支持动态网站）

        Args:
            url: 目标 URL
            wait_time: 等待 JS 渲染的时间（秒）

        Returns:
            渲染后的完整 HTML
        """
        from DrissionPage import ChromiumPage

        page = ChromiumPage()
        try:
            page.get(url)
            page.wait(wait_time)
            return page.html
        finally:
            page.quit()

    @abstractmethod
    async def fetch(self, source_config: dict) -> list[ContentItem]:
        """
        从指定源采集内容

        Args:
            source_config: 源配置，包含url、时间范围等参数

        Returns:
            采集到的内容项列表
        """

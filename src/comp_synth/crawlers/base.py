from abc import ABC, abstractmethod

import httpx

from comp_synth.config import settings
from comp_synth.schema.content_item import ContentItem


class BaseCrawler(ABC):
    """爬虫基类，定义统一的采集接口"""

    async def _fetch_html(self, url: str) -> str:
        """获取网页 HTML"""
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def _is_summary_enough(self, summary: str) -> bool:
        """判断 summary 是否足够（不为空且长度 > 100）"""
        return bool(summary and len(summary) > 100)

    @abstractmethod
    async def fetch(self, source_config: dict) -> list[ContentItem]:
        """
        从指定源采集内容

        Args:
            source_config: 源配置，包含url、时间范围等参数

        Returns:
            采集到的内容项列表
        """

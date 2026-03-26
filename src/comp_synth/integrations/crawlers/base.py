from abc import ABC, abstractmethod

from comp_synth.core.models.base import ContentItem


class BaseCrawler(ABC):
    """爬虫基类，定义统一的采集接口"""

    @abstractmethod
    async def fetch(self, source_config: dict) -> list[ContentItem]:
        """
        从指定源采集内容

        Args:
            source_config: 源配置，包含url、时间范围等参数

        Returns:
            采集到的内容项列表
        """

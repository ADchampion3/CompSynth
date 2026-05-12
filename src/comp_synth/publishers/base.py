from abc import ABC, abstractmethod


class BasePublisher(ABC):
    """发布器基类，定义统一的发布接口"""

    channel_name: str = ""

    def get_config(self) -> dict:
        """Return publisher-specific config from global settings."""
        return {}

    @abstractmethod
    async def publish(self, report: str, config: dict) -> dict:
        """
        发布报告到目标平台

        Args:
            report: 待发布的报告内容
            config: 平台特定的发布配置

        Returns:
            发布结果，包含状态和详情
        """

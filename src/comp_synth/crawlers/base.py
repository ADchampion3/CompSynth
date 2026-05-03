import asyncio
import time
from abc import ABC, abstractmethod

import httpx
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from comp_synth.config import settings
from comp_synth.schema.content_item import ContentItem


def _log_retry(retry_state) -> None:
    """tenacity before_sleep 回调: 重试前记录日志."""
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "HTTP GET 重试 {attempt}/3, 等待 {wait:.1f}s: {error}",
        attempt=retry_state.attempt_number,
        wait=retry_state.next_action.sleep if retry_state.next_action else 0,
        error=exception,
    )


class BaseCrawler(ABC):
    """爬虫基类，定义统一的采集接口"""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        reraise=True,
        before_sleep=_log_retry,
    )
    async def _fetch_html(self, url: str) -> str:
        """获取网页 HTML（带重试机制）"""
        logger.debug("HTTP GET {url} (timeout={timeout}s)", url=url, timeout=settings.request_timeout)
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            elapsed = time.monotonic() - start
            logger.debug("HTTP GET {url} → {status} ({elapsed:.1f}s, {size} bytes)", url=url, status=response.status_code, elapsed=elapsed, size=len(response.text))
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
        logger.info("Browser GET {url} (wait={wait}s, timeout=60s)", url=url, wait=wait_time)
        start = time.monotonic()

        from DrissionPage import ChromiumPage

        def _sync_fetch():
            page = ChromiumPage()
            try:
                page.get(url)
                page.wait(wait_time)
                return page.html
            finally:
                page.quit()

        loop = asyncio.get_event_loop()
        html = await asyncio.wait_for(
            loop.run_in_executor(None, _sync_fetch),
            timeout=60,
        )
        elapsed = time.monotonic() - start
        logger.info("Browser GET {url} → {size} bytes ({elapsed:.1f}s)", url=url, size=len(html), elapsed=elapsed)
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

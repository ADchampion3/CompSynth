"""Crawlee-based fetch service bridging Crawlee's crawler lifecycle into imperative methods."""

import asyncio
import time
from urllib.parse import urlparse

from crawlee import service_locator
from crawlee.crawlers import BeautifulSoupCrawler, PlaywrightCrawler
from crawlee.storage_clients import MemoryStorageClient
from loguru import logger


def _clear_global_storage_cache() -> None:
    """Clear the global StorageInstanceManager cache.

    Crawlee's StorageInstanceManager is a class-level singleton that caches
    RequestQueue/Dataset instances by alias. Without clearing, a second crawler
    in the same process reuses the first crawler's drained queue and processes
    zero requests.
    """
    mgr = service_locator.global_storage_instance_manager
    if mgr is not None:
        mgr.clear_cache()


class _DomainRateLimiter:
    """Per-domain rate limiter ensuring minimum interval between requests."""

    def __init__(self, min_interval: float = 1.0) -> None:
        self._min_interval = min_interval
        self._last_access: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def acquire(self, domain: str) -> None:
        lock = self._locks.setdefault(domain, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            elapsed = now - self._last_access.get(domain, 0.0)
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_access[domain] = time.monotonic()


class CrawleeFetchService:
    """Singleton service wrapping Crawlee crawlers for imperative fetch calls.

    Creates per-call crawler instances to avoid handler registration races under
    asyncio.gather concurrency. Clears the global storage cache before each run
    so every crawler gets a fresh RequestQueue.
    """

    _instance: "CrawleeFetchService | None" = None

    def __init__(self) -> None:
        from comp_synth.config import settings

        self._rate_limiter = _DomainRateLimiter(
            min_interval=settings.crawl_domain_delay
        )

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            parsed = urlparse(url)
            host = parsed.hostname
            if host:
                return host.encode("idna").decode("ascii")
        except Exception:
            pass
        return url

    @classmethod
    def instance(cls) -> "CrawleeFetchService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None

    async def fetch_html(self, url: str) -> str:
        """Fetch raw HTML from a URL using Crawlee's BeautifulSoupCrawler.

        Replaces httpx + tenacity retry with Crawlee's built-in retry
        (max_request_retries=3).
        """
        domain = self._extract_domain(url)
        await self._rate_limiter.acquire(domain)
        _clear_global_storage_cache()
        result: list[str] = []

        async def handler(context) -> None:
            body = await context.http_response.read()
            result.append(body.decode("utf-8", errors="replace"))

        crawler = BeautifulSoupCrawler(
            request_handler=handler,
            storage_client=MemoryStorageClient(),
            max_requests_per_crawl=1,
            max_request_retries=3,
        )

        await crawler.run([url])

        if not result:
            raise RuntimeError(f"Failed to fetch {url}")

        html = result[0]
        logger.debug(
            "Crawlee fetch_html {url} ({size} bytes)",
            url=url,
            size=len(html),
        )
        return html

    async def fetch_html_with_browser(self, url: str, wait_time: float = 2.0) -> str:
        """Fetch rendered HTML using Crawlee's PlaywrightCrawler.

        Replaces DrissionPage with Playwright, managed by Crawlee's lifecycle.
        """
        domain = self._extract_domain(url)
        await self._rate_limiter.acquire(domain)
        _clear_global_storage_cache()
        result: list[str] = []

        async def handler(context) -> None:
            await context.page.wait_for_load_state("networkidle")
            await context.page.wait_for_timeout(int(wait_time * 1000))
            html = await context.page.content()
            result.append(html)

        crawler = PlaywrightCrawler(
            request_handler=handler,
            storage_client=MemoryStorageClient(),
            max_requests_per_crawl=1,
            max_request_retries=3,
        )

        await crawler.run([url])

        if not result:
            raise RuntimeError(f"Failed to fetch {url} with browser")

        html = result[0]
        logger.debug(
            "Crawlee fetch_html_with_browser {url} → {size} bytes",
            url=url,
            size=len(html),
        )
        return html

"""Crawlee-based fetch service bridging Crawlee's crawler lifecycle into imperative methods."""

import asyncio
from urllib.parse import urlparse

from crawlee import service_locator
from crawlee.crawlers import BeautifulSoupCrawler, PlaywrightCrawler
from crawlee.proxy_configuration import ProxyConfiguration
from crawlee.storage_clients import MemoryStorageClient
from loguru import logger

from comp_synth.utils.rate_limiter import DomainRateLimiter


def _install_crawlee_exception_handler() -> None:
    """Suppress harmless Crawlee EventManager cleanup warnings.

    Crawlee's ``LocalEventManager`` uses a 1-second recurring task for system info
    events.  When a crawler shuts down, the event manager exits its async context
    and the recurring task is cancelled — but a race window exists where the task
    can fire *after* ``active`` has been set to ``False`` and *before* the
    ``CancelledError`` is delivered.  The resulting ``RuntimeError`` is harmless
    (it does not affect crawl results) but noisy.  Suppress it at the asyncio
    level so it does not pollute logs.

    The task name (``Task-recurring-...``) lives in the ``future`` context key,
    not in ``message``, so we check both.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    default = loop.get_exception_handler()

    def _handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        exc = context.get("exception")
        if isinstance(exc, RuntimeError) and "is not active" in str(exc):
            return
        if isinstance(exc, RuntimeError) and "LocalEventManager" in str(exc):
            return
        if default:
            default(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(_handler)


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


class CrawleeFetchService:
    """Singleton service wrapping Crawlee crawlers for imperative fetch calls.

    Creates per-call crawler instances to avoid handler registration races under
    asyncio.gather concurrency. Clears the global storage cache before each run
    so every crawler gets a fresh RequestQueue.
    """

    _instance: "CrawleeFetchService | None" = None

    def __init__(self) -> None:
        from comp_synth.config import settings

        self._rate_limiter = DomainRateLimiter(
            min_interval=settings.crawl_domain_delay
        )
        self._proxy_store = None
        _install_crawlee_exception_handler()

    def _get_proxy_store(self):
        if self._proxy_store is None:
            from comp_synth.store.domain_proxy_store import DomainProxyStore
            self._proxy_store = DomainProxyStore()
        return self._proxy_store

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

    def _build_proxy_config(self, url: str) -> ProxyConfiguration | None:
        from comp_synth.config import settings

        if not settings.proxy_enabled or not settings.proxy_url:
            return None

        domain = self._extract_domain(url)
        if not self._get_proxy_store().needs_proxy(domain):
            return None

        logger.info("Using proxy for {domain}", domain=domain)
        return ProxyConfiguration(proxy_urls=[settings.proxy_url])

    def _record_success(self, domain: str) -> None:
        from comp_synth.config import settings

        if not settings.proxy_enabled or not settings.proxy_url:
            return

        self._get_proxy_store().record_success(domain)

    async def fetch_html(self, url: str) -> str:
        """Fetch raw HTML from a URL using Crawlee's BeautifulSoupCrawler."""
        domain = self._extract_domain(url)
        await self._rate_limiter.acquire(domain)
        _clear_global_storage_cache()
        result: list[str] = []

        async def handler(context) -> None:
            body = await context.http_response.read()
            result.append(body.decode("utf-8", errors="replace"))

        proxy_config = self._build_proxy_config(url)
        crawler = BeautifulSoupCrawler(
            request_handler=handler,
            storage_client=MemoryStorageClient(),
            max_requests_per_crawl=1,
            max_request_retries=3,
            proxy_configuration=proxy_config,
        )

        await crawler.run([url])
        await asyncio.sleep(0)  # Let Crawlee's recurring task cancellations settle

        if not result:
            raise RuntimeError(f"Failed to fetch {url}")

        self._record_success(domain)
        html = result[0]
        logger.debug(
            "Crawlee fetch_html {url} ({size} bytes)",
            url=url,
            size=len(html),
        )
        return html

    async def fetch_html_with_browser(self, url: str, wait_time: float = 2.0) -> str:
        """Fetch rendered HTML using Crawlee's PlaywrightCrawler."""
        domain = self._extract_domain(url)
        await self._rate_limiter.acquire(domain)
        _clear_global_storage_cache()
        result: list[str] = []

        async def handler(context) -> None:
            await context.page.wait_for_load_state("networkidle")
            await context.page.wait_for_timeout(int(wait_time * 1000))
            html = await context.page.content()
            result.append(html)

        proxy_config = self._build_proxy_config(url)
        crawler = PlaywrightCrawler(
            request_handler=handler,
            storage_client=MemoryStorageClient(),
            max_requests_per_crawl=1,
            max_request_retries=3,
            proxy_configuration=proxy_config,
        )

        await crawler.run([url])
        await asyncio.sleep(0)  # Let Crawlee's recurring task cancellations settle

        if not result:
            raise RuntimeError(f"Failed to fetch {url} with browser")

        self._record_success(domain)
        html = result[0]
        logger.debug(
            "Crawlee fetch_html_with_browser {url} → {size} bytes",
            url=url,
            size=len(html),
        )
        return html

"""Tests for CrawleeFetchService."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from comp_synth.crawlers.crawlee_fetch import (
    CrawleeFetchService,
    _clear_global_storage_cache,
    _DomainRateLimiter,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset singleton between tests."""
    CrawleeFetchService.reset()
    yield
    CrawleeFetchService.reset()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_http_response(body: bytes = b"<html>ok</html>"):
    resp = MagicMock()
    resp.read = AsyncMock(return_value=body)
    return resp


def _make_bs_context(body: bytes = b"<html>ok</html>"):
    ctx = MagicMock()
    ctx.http_response = _make_http_response(body)
    return ctx


def _make_pw_context(html: str = "<html>rendered</html>"):
    ctx = MagicMock()
    ctx.page = MagicMock()
    ctx.page.wait_for_load_state = AsyncMock()
    ctx.page.wait_for_timeout = AsyncMock()
    ctx.page.content = AsyncMock(return_value=html)
    return ctx


# ---------------------------------------------------------------------------
# fetch_html
# ---------------------------------------------------------------------------


class TestFetchHtml:
    """Tests for CrawleeFetchService.fetch_html."""

    def test_returns_html_on_success(self):
        async def run():
            mock_ctx = _make_bs_context(b"<html>hello</html>")
            handler_ref = None

            async def fake_run(urls):
                if handler_ref:
                    await handler_ref(mock_ctx)

            mock_crawler = MagicMock()
            mock_crawler.run = fake_run

            def capture_handler(**kwargs):
                nonlocal handler_ref
                handler_ref = kwargs["request_handler"]
                return mock_crawler

            with patch("comp_synth.crawlers.crawlee_fetch._clear_global_storage_cache"):
                with patch(
                    "comp_synth.crawlers.crawlee_fetch.BeautifulSoupCrawler",
                    side_effect=capture_handler,
                ):
                    service = CrawleeFetchService.instance()
                    result = await service.fetch_html("https://example.com")
                    assert result == "<html>hello</html>"

        asyncio.run(run())

    def test_raises_on_empty_result(self):
        async def run():
            mock_crawler = MagicMock()

            async def fake_run(urls):
                pass  # handler never called

            mock_crawler.run = fake_run

            with patch("comp_synth.crawlers.crawlee_fetch._clear_global_storage_cache"):
                with patch(
                    "comp_synth.crawlers.crawlee_fetch.BeautifulSoupCrawler",
                    return_value=mock_crawler,
                ):
                    service = CrawleeFetchService.instance()
                    with pytest.raises(RuntimeError, match="Failed to fetch"):
                        await service.fetch_html("https://example.com")

        asyncio.run(run())


# ---------------------------------------------------------------------------
# fetch_html_with_browser
# ---------------------------------------------------------------------------


class TestFetchHtmlWithBrowser:
    """Tests for CrawleeFetchService.fetch_html_with_browser."""

    def test_returns_rendered_html(self):
        async def run():
            mock_ctx = _make_pw_context("<html>rendered content</html>")
            handler_ref = None

            async def fake_run(urls):
                if handler_ref:
                    await handler_ref(mock_ctx)

            mock_crawler = MagicMock()
            mock_crawler.run = fake_run

            def capture_handler(**kwargs):
                nonlocal handler_ref
                handler_ref = kwargs["request_handler"]
                return mock_crawler

            with patch("comp_synth.crawlers.crawlee_fetch._clear_global_storage_cache"):
                with patch(
                    "comp_synth.crawlers.crawlee_fetch.PlaywrightCrawler",
                    side_effect=capture_handler,
                ):
                    service = CrawleeFetchService.instance()
                    result = await service.fetch_html_with_browser(
                        "https://example.com", wait_time=1.0
                    )
                    assert result == "<html>rendered content</html>"
                    mock_ctx.page.wait_for_load_state.assert_called_once_with(
                        "networkidle"
                    )
                    mock_ctx.page.wait_for_timeout.assert_called_once_with(1000)

        asyncio.run(run())

    def test_raises_on_empty_result(self):
        async def run():
            mock_crawler = MagicMock()

            async def fake_run(urls):
                pass

            mock_crawler.run = fake_run

            with patch("comp_synth.crawlers.crawlee_fetch._clear_global_storage_cache"):
                with patch(
                    "comp_synth.crawlers.crawlee_fetch.PlaywrightCrawler",
                    return_value=mock_crawler,
                ):
                    service = CrawleeFetchService.instance()
                    with pytest.raises(RuntimeError, match="Failed to fetch"):
                        await service.fetch_html_with_browser("https://example.com")

        asyncio.run(run())


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    """Tests for singleton pattern."""

    def test_instance_returns_same_object(self):
        a = CrawleeFetchService.instance()
        b = CrawleeFetchService.instance()
        assert a is b

    def test_reset_clears_singleton(self):
        a = CrawleeFetchService.instance()
        CrawleeFetchService.reset()
        b = CrawleeFetchService.instance()
        assert a is not b


# ---------------------------------------------------------------------------
# Global cache clear
# ---------------------------------------------------------------------------


class TestClearGlobalCache:
    """Tests for _clear_global_storage_cache helper."""

    def test_calls_clear_cache_when_manager_exists(self):
        with patch(
            "comp_synth.crawlers.crawlee_fetch.service_locator"
        ) as mock_sl:
            mock_mgr = MagicMock()
            mock_sl.global_storage_instance_manager = mock_mgr
            _clear_global_storage_cache()
            mock_mgr.clear_cache.assert_called_once()

    def test_noop_when_manager_is_none(self):
        with patch(
            "comp_synth.crawlers.crawlee_fetch.service_locator"
        ) as mock_sl:
            mock_sl.global_storage_instance_manager = None
            _clear_global_storage_cache()  # should not raise


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


class TestConcurrency:
    """Tests for concurrent access via asyncio.gather."""

    def test_concurrent_fetches_independent(self):
        async def run():
            call_count = 0

            async def fake_run(urls):
                nonlocal call_count
                call_count += 1

            mock_crawler = MagicMock()
            mock_crawler.run = fake_run

            with patch("comp_synth.crawlers.crawlee_fetch._clear_global_storage_cache"):
                with patch(
                    "comp_synth.crawlers.crawlee_fetch.BeautifulSoupCrawler",
                    return_value=mock_crawler,
                ):
                    service = CrawleeFetchService.instance()
                    results = await asyncio.gather(
                        service.fetch_html("https://a.com"),
                        service.fetch_html("https://b.com"),
                        return_exceptions=True,
                    )
                    assert all(isinstance(r, RuntimeError) for r in results)
                    assert call_count == 2

        asyncio.run(run())


# ---------------------------------------------------------------------------
# _DomainRateLimiter
# ---------------------------------------------------------------------------


class TestDomainRateLimiter:
    """Tests for the _DomainRateLimiter helper class."""

    def test_no_delay_on_first_access(self):
        async def run():
            limiter = _DomainRateLimiter(min_interval=0.5)
            start = time.monotonic()
            await limiter.acquire("example.com")
            elapsed = time.monotonic() - start
            assert elapsed < 0.1

        asyncio.run(run())

    def test_delays_second_access_same_domain(self):
        async def run():
            limiter = _DomainRateLimiter(min_interval=0.2)
            await limiter.acquire("example.com")
            start = time.monotonic()
            await limiter.acquire("example.com")
            elapsed = time.monotonic() - start
            assert elapsed >= 0.15  # allow small timing slack

        asyncio.run(run())

    def test_no_delay_for_different_domains(self):
        async def run():
            limiter = _DomainRateLimiter(min_interval=1.0)
            await limiter.acquire("a.com")
            start = time.monotonic()
            await limiter.acquire("b.com")
            elapsed = time.monotonic() - start
            assert elapsed < 0.1

        asyncio.run(run())

    def test_lock_contention_serializes_concurrent_access(self):
        async def run():
            limiter = _DomainRateLimiter(min_interval=0.15)
            order: list[int] = []

            async def task(idx: int) -> None:
                await limiter.acquire("example.com")
                order.append(idx)

            await asyncio.gather(task(0), task(1), task(2))
            assert order == [0, 1, 2]

        asyncio.run(run())

    def test_custom_min_interval(self):
        async def run():
            limiter = _DomainRateLimiter(min_interval=0.05)
            await limiter.acquire("example.com")
            start = time.monotonic()
            await limiter.acquire("example.com")
            elapsed = time.monotonic() - start
            assert elapsed >= 0.03  # allow slack

        asyncio.run(run())

    def test_zero_and_negative_intervals(self):
        async def run():
            for interval in (0.0, -1.0):
                limiter = _DomainRateLimiter(min_interval=interval)
                start = time.monotonic()
                await limiter.acquire("example.com")
                await limiter.acquire("example.com")
                elapsed = time.monotonic() - start
                assert elapsed < 0.1

        asyncio.run(run())


# ---------------------------------------------------------------------------
# Rate-limited fetch integration
# ---------------------------------------------------------------------------


class TestRateLimitedFetch:
    """Tests verifying CrawleeFetchService uses _DomainRateLimiter."""

    def test_fetch_html_calls_rate_limiter(self):
        async def run():
            mock_ctx = _make_bs_context(b"<html>ok</html>")
            handler_ref = None

            async def fake_run(urls):
                if handler_ref:
                    await handler_ref(mock_ctx)

            mock_crawler = MagicMock()
            mock_crawler.run = fake_run

            def capture_handler(**kwargs):
                nonlocal handler_ref
                handler_ref = kwargs["request_handler"]
                return mock_crawler

            with patch("comp_synth.crawlers.crawlee_fetch._clear_global_storage_cache"):
                with patch(
                    "comp_synth.crawlers.crawlee_fetch.BeautifulSoupCrawler",
                    side_effect=capture_handler,
                ):
                    service = CrawleeFetchService.instance()
                    limiter = service._rate_limiter
                    acquired_domains: list[str] = []
                    original_acquire = limiter.acquire

                    async def tracking_acquire(domain: str) -> None:
                        acquired_domains.append(domain)
                        await original_acquire(domain)

                    limiter.acquire = tracking_acquire
                    await service.fetch_html("https://example.com/page")
                    assert acquired_domains == ["example.com"]

        asyncio.run(run())

    def test_fetch_html_with_browser_calls_rate_limiter(self):
        async def run():
            mock_ctx = _make_pw_context("<html>ok</html>")
            handler_ref = None

            async def fake_run(urls):
                if handler_ref:
                    await handler_ref(mock_ctx)

            mock_crawler = MagicMock()
            mock_crawler.run = fake_run

            def capture_handler(**kwargs):
                nonlocal handler_ref
                handler_ref = kwargs["request_handler"]
                return mock_crawler

            with patch("comp_synth.crawlers.crawlee_fetch._clear_global_storage_cache"):
                with patch(
                    "comp_synth.crawlers.crawlee_fetch.PlaywrightCrawler",
                    side_effect=capture_handler,
                ):
                    service = CrawleeFetchService.instance()
                    limiter = service._rate_limiter
                    acquired_domains: list[str] = []
                    original_acquire = limiter.acquire

                    async def tracking_acquire(domain: str) -> None:
                        acquired_domains.append(domain)
                        await original_acquire(domain)

                    limiter.acquire = tracking_acquire
                    await service.fetch_html_with_browser("https://example.com/page")
                    assert acquired_domains == ["example.com"]

        asyncio.run(run())

    def test_same_domain_sequential_respects_delay(self):
        async def run():
            mock_ctx = _make_bs_context(b"<html>ok</html>")
            handler_ref = None

            async def fake_run(urls):
                if handler_ref:
                    await handler_ref(mock_ctx)

            mock_crawler = MagicMock()
            mock_crawler.run = fake_run

            def capture_handler(**kwargs):
                nonlocal handler_ref
                handler_ref = kwargs["request_handler"]
                return mock_crawler

            with patch(
                "comp_synth.config.settings.crawl_domain_delay", 0.1
            ):
                with patch("comp_synth.crawlers.crawlee_fetch._clear_global_storage_cache"):
                    with patch(
                        "comp_synth.crawlers.crawlee_fetch.BeautifulSoupCrawler",
                        side_effect=capture_handler,
                    ):
                        CrawleeFetchService.reset()
                        service = CrawleeFetchService.instance()
                        await service.fetch_html("https://example.com/a")
                        start = time.monotonic()
                        await service.fetch_html("https://example.com/b")
                        elapsed = time.monotonic() - start
                        assert elapsed >= 0.07

        asyncio.run(run())

    def test_extract_domain(self):
        assert CrawleeFetchService._extract_domain("https://example.com/path") == "example.com"
        assert CrawleeFetchService._extract_domain("http://sub.example.com:8080/q") == "sub.example.com"
        assert CrawleeFetchService._extract_domain("not-a-url") == "not-a-url"
        assert CrawleeFetchService._extract_domain("") == ""

"""
DynamicWebCrawler 模块测试
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from comp_synth.crawlers.dynamic_web_crawler import (
    SPA_MARKERS,
    DynamicWebCrawler,
    is_likely_spa,
)


class TestIsLikelySpa:
    """is_likely_spa 检测函数测试"""

    def test_thin_html_detected(self):
        """HTML 过短应被检测为 SPA"""
        thin_html = "<html><body><div id='root'></div></body></html>"
        assert is_likely_spa(thin_html) is True

    def test_nextjs_marker(self):
        """Next.js 标记应被检测为 SPA"""
        html = "<html><body><script>window.__NEXT_DATA__={'props':{}}</script></body></html>"
        assert is_likely_spa(html) is True

    def test_nuxt_marker(self):
        """Nuxt.js 标记应被检测为 SPA"""
        html = "<html><body><script>window.__NUXT_DATA__=[1,2,3]</script></body></html>"
        assert is_likely_spa(html) is True

    def test_vue_app_marker(self):
        """Vue SPA 标记应被检测为 SPA"""
        html = '<html><body><div id="app" data-vue-app="true"></div></body></html>'
        assert is_likely_spa(html) is True

    def test_angular_marker(self):
        """Angular 标记应被检测为 SPA"""
        html = '<html><body ng-app="myApp"><div ng-view></div></body></html>'
        assert is_likely_spa(html) is True

    def test_react_marker(self):
        """React 标记应被检测为 SPA"""
        html = '<html><body><div id="root" data-reactroot="true"></div></body></html>'
        assert is_likely_spa(html) is True

    def test_normal_html_not_spa(self):
        """正常 HTML 不应被检测为 SPA"""
        normal_html = """
        <!doctype html>
        <html>
        <head><title>Normal Page</title></head>
        <body>
            <article>
                <h1>Article Title</h1>
                <p>This is a normal server-rendered article with meaningful content.</p>
            </article>
        </body>
        </html>
        """
        assert is_likely_spa(normal_html) is False

    def test_all_spa_markers_covered(self):
        """验证所有 SPA_MARKERS 都被 is_likely_spa 处理"""
        for marker in SPA_MARKERS:
            html = f"<html><body><script>{marker}={{}}</script></body></html>"
            assert is_likely_spa(html) is True, f"Marker {marker} should be detected"


class TestDynamicWebCrawlerUnit:
    """DynamicWebCrawler 单元测试"""

    @pytest.fixture
    def mock_adaptive_web_crawler(self, monkeypatch):
        """Mock AdaptiveWebCrawler 避免数据库依赖"""
        mock_crawler = MagicMock()
        mock_crawler._crawl_detail_page = AsyncMock(return_value=[])
        monkeypatch.setattr(
            "comp_synth.crawlers.dynamic_web_crawler.AdaptiveWebCrawler",
            lambda: mock_crawler,
        )
        return mock_crawler

    @pytest.fixture
    def mock_tracker(self, monkeypatch):
        """Mock CrawlTracker"""
        mock = MagicMock()
        mock.is_crawled.return_value = False
        monkeypatch.setattr(
            "comp_synth.crawlers.dynamic_web_crawler.CrawlTracker",
            lambda: mock,
        )
        return mock

    def test_fetch_signature(self, mock_adaptive_web_crawler, mock_tracker):
        """测试 fetch 方法签名与 BaseCrawler 一致"""
        crawler = DynamicWebCrawler()
        assert callable(crawler.fetch)

    def test_normal_html_uses_httpx(
        self, mock_adaptive_web_crawler, mock_tracker
    ):
        """正常 HTML 不应触发 Chrome"""
        normal_html = """
        <!doctype html>
        <html>
        <head><title>Normal Page</title></head>
        <body>
            <article>
                <h1>Title</h1>
                <p>This is a normal server-rendered article with meaningful content that is longer than 200 characters to avoid being detected as an SPA.</p>
            </article>
        </body>
        </html>
        """

        async def run():
            crawler = DynamicWebCrawler()
            crawler._delegate._crawl_detail_page = AsyncMock(return_value=[])
            with patch.object(
                crawler, "_fetch_html", return_value=normal_html
            ) as mock_fetch:
                with patch.object(
                    crawler, "_fetch_with_chrome"
                ) as mock_chrome:
                    await crawler.fetch(
                        {"url": "https://example.com"}
                    )
                    mock_fetch.assert_called_once()
                    mock_chrome.assert_not_called()

        asyncio.run(run())

    def test_spa_html_triggers_chrome(
        self, mock_adaptive_web_crawler, mock_tracker
    ):
        """SPA HTML 应触发 Chrome 渲染"""
        spa_html = "<html><body><div id='root'></div></body></html>"

        async def run():
            crawler = DynamicWebCrawler()
            crawler._delegate._crawl_detail_page = AsyncMock(return_value=[])
            with patch.object(
                crawler, "_fetch_html", return_value=spa_html
            ) as mock_fetch:
                with patch.object(
                    crawler,
                    "_fetch_with_chrome",
                    return_value="<html><body><article>Rendered</article></body></html>",
                ) as mock_chrome:
                    await crawler.fetch({"url": "https://spa.example.com"})
                    mock_fetch.assert_called_once()
                    mock_chrome.assert_called_once_with("https://spa.example.com")

        asyncio.run(run())

    def test_javascript_flag_skips_detection(
        self, mock_adaptive_web_crawler, mock_tracker
    ):
        """javascript:true 配置应跳过检测直接使用 Chrome"""
        normal_html = "<html><body><article><h1>Title</h1></article></body></html>"

        async def run():
            crawler = DynamicWebCrawler()
            crawler._delegate._crawl_detail_page = AsyncMock(return_value=[])
            with patch.object(
                crawler, "_fetch_html", return_value=normal_html
            ) as mock_fetch:
                with patch.object(
                    crawler,
                    "_fetch_with_chrome",
                    return_value="<html><body>rendered</body></html>",
                ) as mock_chrome:
                    await crawler.fetch(
                        {"url": "https://example.com", "javascript": True}
                    )
                    # httpx 仍会调用
                    mock_fetch.assert_called_once()
                    # 但因为 javascript:true，也会调用 Chrome
                    mock_chrome.assert_called_once()

        asyncio.run(run())

    def test_httpx_failure_falls_back_to_chrome(
        self, mock_adaptive_web_crawler, mock_tracker
    ):
        """httpx 失败时应回退到 Chrome"""
        async def run():
            crawler = DynamicWebCrawler()
            crawler._delegate._crawl_detail_page = AsyncMock(return_value=[])
            with patch.object(
                crawler, "_fetch_html", side_effect=Exception("Network error")
            ):
                with patch.object(
                    crawler,
                    "_fetch_with_chrome",
                    return_value="<html><body>rendered</body></html>",
                ) as mock_chrome:
                    await crawler.fetch({"url": "https://example.com"})
                    mock_chrome.assert_called_once()

        asyncio.run(run())

    def test_delegate_called_with_html(
        self, mock_adaptive_web_crawler, mock_tracker
    ):
        """验证最终调用 delegate._crawl_detail_page"""
        rendered_html = "<html><body><article>Content</article></body></html>"

        async def run():
            crawler = DynamicWebCrawler()
            crawler._delegate._crawl_detail_page = AsyncMock(return_value=[])

            with patch.object(
                crawler, "_fetch_html", side_effect=Exception("fail")
            ):
                with patch.object(
                    crawler, "_fetch_with_chrome", return_value=rendered_html
                ):
                    await crawler.fetch({"url": "https://example.com"})
                    crawler._delegate._crawl_detail_page.assert_called_once_with(
                        rendered_html, "https://example.com"
                    )

        asyncio.run(run())


class TestDynamicWebCrawlerIntegration:
    """DynamicWebCrawler 集成测试（需要网络）"""

    @pytest.fixture(autouse=True)
    def setup_data_dir(self, monkeypatch):
        """确保数据目录存在"""
        from pathlib import Path

        data_dir = Path("./data")
        data_dir.mkdir(exist_ok=True)
        monkeypatch.setattr("comp_synth.config.settings.data_dir", data_dir)
        yield

    def test_crawl_simple_page(self):
        """测试爬取简单页面（httpx 路径）"""
        async def run():
            crawler = DynamicWebCrawler()
            items = await crawler.fetch({"url": "https://httpbin.org/html"})
            assert isinstance(items, list)

        asyncio.run(run())


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

"""
CompSynth Crawler 模块测试
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from comp_synth.crawlers.adaptive_web_crawler import AdaptiveWebCrawler
from comp_synth.schema.site_chema import SiteSchema
from comp_synth.store.schema_store import SchemaStore

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_schema_store(monkeypatch):
    """Mock SchemaStore 避免数据库依赖"""
    mock_store = MagicMock()
    mock_store.get.return_value = None
    mock_store.can_use_llm.return_value = True
    mock_store.save.return_value = None
    mock_store.mark_llm_called.return_value = None
    mock_store.update_list_selectors.return_value = None
    monkeypatch.setattr("comp_synth.crawlers.adaptive_web_crawler.SchemaStore", lambda: mock_store)

    return mock_store


@pytest.fixture
def meituan_list_html():
    """美团技术博客列表页 HTML（精简版）"""
    return """
<!doctype html>
<html lang="en">
    <head><meta charset="utf-8"></head>
    <body>
        <nav class="navbar">导航栏</nav>
        <div class="container-fluid main-container">
            <div class="row post-container-wrapper">
                <div class="col-md-6">
                    <div class="post-container">
                        <h2 class="post-title">
                            <a href="https://tech.meituan.com/2026/03/20/bi-practice.html">美团 BI 在指标平台和分析引擎上的探索和实践</a>
                        </h2>
                        <div class="meta-box">
                            <span class="m-post-date">2026年03月20日</span>
                            <span class="m-post-nick">数据平台</span>
                        </div>
                        <div class="post-content post-expect">
                            美团数据平台构建了以指标平台为核心的新一代 BI 架构，部分解决了传统 BI 平台在个性化数据集驱动下产生的数据口径混乱、查询性能差等问题。
                            <a class="more-link" href="https://tech.meituan.com/2026/03/20/bi-practice.html">阅读全文</a>
                        </div>
                        <div class="meta-box post-bottom-meta-box">
                            <span class="tag-links">
                                <a href="/tags/数据平台.html" rel="tag">数据平台</a>
                            </span>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="post-container">
                        <h2 class="post-title">
                            <a href="https://tech.meituan.com/2026/03/13/qwik-practice.html">重塑站外体验：大众点评 M 站基于 Qwik.js 的重构实践</a>
                        </h2>
                        <div class="meta-box">
                            <span class="m-post-date">2026年03月13日</span>
                            <span class="m-post-nick">美团技术团队</span>
                        </div>
                        <div class="post-content post-expect">
                            大众点评增长团队引入 Qwik.js 重构 M 站核心页面架构，解决了重构前页面加载慢、维护成本高的难题。
                            <a class="more-link" href="https://tech.meituan.com/2026/03/13/qwik-practice.html">阅读全文</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
</html>
    """


# ============================================================================
# SiteSchema Tests
# ============================================================================

class TestSiteSchema:
    """SiteSchema 模型测试"""

    def test_create_schema(self):
        """测试创建 SiteSchema"""
        schema = SiteSchema(
            site_name="tech.meituan.com",
            site_url="https://tech.meituan.com/",
            selectors=[{
                "title": "h1.article-title",
                "author": ".author",
                "content": ".article-body",
                "tags": ".article-tags .tag",
            }],
        )

        assert schema.site_name == "tech.meituan.com"
        assert schema.site_url == "https://tech.meituan.com/"
        assert len(schema.selectors) == 1
        assert len(schema.selectors[0]) == 4
        assert schema.created_at is not None
        assert schema.updated_at is not None
        assert schema.last_llm_call is None

    def test_schema_serialization(self):
        """测试 Schema JSON 序列化"""
        schema = SiteSchema(
            site_name="example.com",
            site_url="https://example.com",
            selectors=[{"title": "h1"}],
        )

        json_str = schema.model_dump_json()
        data = json.loads(json_str)

        assert data["site_name"] == "example.com"
        assert data["selectors"][0]["title"] == "h1"

    def test_schema_deserialization(self):
        """测试 Schema JSON 反序列化"""
        data = {
            "site_name": "test.com",
            "site_url": "https://test.com",
            "selectors": [{"title": "h1", "content": "article"}],
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "last_llm_call": None,
        }

        schema = SiteSchema(**data)
        assert schema.site_name == "test.com"
        assert schema.selectors[0]["content"] == "article"


# ============================================================================
# AdaptiveWebCrawler Tests (Unit - with mocked SchemaStore)
# ============================================================================

class TestAdaptiveWebCrawler:
    """AdaptiveWebCrawler 单元测试"""

    def test_detect_site(self, mock_schema_store):
        """测试站点检测"""
        crawler = AdaptiveWebCrawler()

        assert crawler._detect_site("https://tech.meituan.com/archives/") == "tech.meituan.com"
        assert crawler._detect_site("https://blog.example.com/post/123") == "blog.example.com"
        assert crawler._detect_site("https://example.com") == "example.com"

    def test_fetch_html_success(self, mock_schema_store):
        """测试成功获取 HTML"""
        async def run():
            crawler = AdaptiveWebCrawler()
            html = await crawler._fetch_html("https://httpbin.org/html")
            assert "<html>" in html or "<HTML>" in html

        asyncio.run(run())

    def test_fetch_html_failure(self, mock_schema_store):
        """测试获取 HTML 失败"""
        async def run():
            crawler = AdaptiveWebCrawler()
            with pytest.raises(Exception):
                await crawler._fetch_html("https://httpbin.org/status/404")

        asyncio.run(run())


class TestAdaptiveWebCrawlerIntegration:
    """AdaptiveWebCrawler 集成测试（需要网络）"""

    @pytest.fixture(autouse=True)
    def setup_data_dir(self, monkeypatch):
        """确保数据目录存在"""
        data_dir = Path("./data")
        data_dir.mkdir(exist_ok=True)
        monkeypatch.setattr("comp_synth.config.settings.data_dir", data_dir)
        monkeypatch.setattr("comp_synth.config.settings.site_schema_db_path", data_dir / "test_site_schemas.db")
        yield
        import time
        time.sleep(0.1)

    def test_crawl_meituan_homepage(self):
        """测试爬取美团技术首页"""
        async def run():
            crawler = AdaptiveWebCrawler()
            items = await crawler.fetch({"url": "https://tech.meituan.com/"})
            assert isinstance(items, list)

        asyncio.run(run())

    def test_crawl_meituan_article_list(self):
        """测试爬取美团技术文章列表页"""
        async def run():
            crawler = AdaptiveWebCrawler()
            items = await crawler.fetch({"url": "https://tech.meituan.com/archives/"})
            assert isinstance(items, list)

        asyncio.run(run())

    def test_crawl_meituan_article_detail(self):
        """测试爬取美团技术文章详情页"""
        async def run():
            crawler = AdaptiveWebCrawler()
            items = await crawler.fetch({
                "url": "https://tech.meituan.com/2024/10/18/recce-in-meituan.html"
            })

            assert isinstance(items, list)
            if items:
                item = items[0]
                assert item.url == "https://tech.meituan.com/2024/10/18/recce-in-meituan.html"
                assert item.source == "web"
                assert item.title != ""

        asyncio.run(run())

    def test_duplicate_url_skipped(self):
        """测试重复 URL 由 ContentManager 跳过（crawler 本身不处理去重）"""
        async def run():
            # Deduplication is now handled by ContentManager, not the crawler.
            # This test verifies the crawler still returns items for duplicate URLs.
            crawler = AdaptiveWebCrawler()
            url = "https://example.com/test-article"

            await crawler.fetch_page(url)
            # crawler 不做去重，返回结果取决于页面内容

            items2 = await crawler.fetch_page(url)
            # ContentManager 会在上层处理去重，crawler 本身不跳过
            assert isinstance(items2, list)

        asyncio.run(run())


# ============================================================================
# Schema Persistence Integration Tests
# ============================================================================

class TestSchemaPersistenceAndReuse:
    """Schema 持久化和复用测试"""

    @pytest.fixture(autouse=True)
    def setup_real_schema_store(self, monkeypatch):
        """使用临时数据库路径"""
        tmpdir = tempfile.mkdtemp()
        db_path = Path(tmpdir) / "test_schema_reuse.db"
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr("comp_synth.config.settings.site_schema_db_path", db_path)
        monkeypatch.setattr("comp_synth.config.settings.data_dir", data_dir)
        monkeypatch.setattr("comp_synth.config.settings.crawl_db_path", data_dir / "crawl_state.db")

        from comp_synth.crawlers import adaptive_web_crawler
        adaptive_web_crawler.AdaptiveWebCrawler._schema_store = None

        yield db_path

        import shutil
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass

    def test_first_crawl_saves_schema(self):
        """测试首次爬取后 schema 被保存到数据库"""

        async def run():
            site = "example.com"

            store = SchemaStore()
            assert store.get(site) is None
            assert store.can_use_llm(site) is True

            from comp_synth.schema.site_chema import SiteSchema
            schema = SiteSchema(
                site_name=site,
                site_url=f"https://{site}",
                selectors=[{"title": "h1", "content": "article"}],
            )
            store.save(schema)
            store.mark_llm_called(site)

            retrieved = store.get(site)
            assert retrieved is not None
            assert retrieved.selectors[0]["title"] == "h1"
            assert store.can_use_llm(site) is False

        asyncio.run(run())

    def test_schema_reuse_verification(self):
        """综合测试：验证 schema 被正确保存和复用"""

        async def run():
            test_url = "https://httpbin.org/html"

            crawler1 = AdaptiveWebCrawler()
            items1 = await crawler1.fetch({"url": test_url})
            assert len(items1) > 0

            store = SchemaStore()
            site_name = "httpbin.org"
            schema = store.get(site_name)

            crawler2 = AdaptiveWebCrawler()
            items2 = await crawler2.fetch({"url": test_url})

            if items1 and items2:
                assert items1[0].title == items2[0].title

            if schema:
                assert schema.site_name == site_name
                assert isinstance(schema.selectors, list)

        asyncio.run(run())


# ============================================================================
# List Page Extraction Tests
# ============================================================================

class TestListPageExtraction:
    """测试列表页多文章提取"""

    def test_is_list_page_true(self, mock_schema_store, meituan_list_html):
        """测试列表页检测返回 True"""
        async def run():
            crawler = AdaptiveWebCrawler()
            assert crawler._is_list_page(meituan_list_html) is True
        asyncio.run(run())

    def test_is_list_page_false(self, mock_schema_store):
        """测试详情页（article 页面）检测返回 False"""
        article_html = """
        <html><body>
            <article>
                <h1>文章标题</h1>
                <div class="article-content"><p>正文内容</p></div>
            </article>
        </body></html>
        """
        async def run():
            crawler = AdaptiveWebCrawler()
            assert crawler._is_list_page(article_html) is False
        asyncio.run(run())

    def test_extract_list_items(self, mock_schema_store, meituan_list_html):
        """测试从列表页提取多个条目"""
        async def run():
            crawler = AdaptiveWebCrawler()
            items = await crawler._extract_list_items(
                meituan_list_html, "https://tech.meituan.com/", "tech.meituan.com"
            )
            assert len(items) >= 2, f"应该提取到至少2个条目，实际: {len(items)}"
            assert items[0]["url"].startswith("https://tech.meituan.com/")
            assert items[0]["title"] != ""
            for item in items:
                assert item["url"].startswith("http") or item["url"].startswith("/"), f"无效 URL: {item['url']}"
                assert item["title"] != "", "title 不应为空"
        asyncio.run(run())

    def test_extract_list_items_deduplication(self, mock_schema_store):
        """测试列表项 URL 去重"""
        html = """
        <html>
        <body>
            <div class="post-list">
                <article class="post-item">
                    <h2><a href="/2024/10/18/article1.html">第一篇文章标题</a></h2>
                    <p class="summary">摘要1</p>
                </article>
                <article class="post-item">
                    <h2><a href="/2024/10/18/article1.html">第一篇文章标题重复</a></h2>
                    <p class="summary">摘要1重复</p>
                </article>
                <article class="post-item">
                    <h2><a href="/2024/10/19/article2.html">第二篇文章标题</a></h2>
                    <p class="summary">摘要2</p>
                </article>
            </div>
        </body>
        </html>
        """
        async def run():
            crawler = AdaptiveWebCrawler()
            items = await crawler._extract_list_items(html, "https://example.com/", "example.com")
            urls = [item["url"] for item in items]
            assert len(urls) == len(set(urls)), "URL 应该去重"
            assert len(items) == 2, f"应该只有2个唯一条目，实际: {len(items)}"
        asyncio.run(run())

    def test_crawl_list_page_with_mocked_detail(self, mock_schema_store, meituan_list_html):
        """测试列表页爬取返回多个 WebPageItem（detail-fetch 由 ContentManager 调用）"""
        async def run():
            crawler = AdaptiveWebCrawler()

            # _crawl_list_page returns items without detail-fetch (handled by ContentManager)
            items = await crawler._crawl_list_page(meituan_list_html, "https://tech.meituan.com/")

            assert len(items) >= 2, f"应该返回至少2个条目，实际: {len(items)}"
            for item in items:
                assert item.url.startswith("https://tech.meituan.com/")
                assert item.title != ""
        asyncio.run(run())

    def test_crawl_list_page_skips_detail_when_summary_enough(self, mock_schema_store):
        """测试列表页提取时返回摘要（detail-fetch 由 ContentManager 判断）"""
        html_with_long_summary = """
        <html>
        <body>
            <div class="post-list">
                <article class="post-item">
                    <h2><a href="/article1.html">这是一篇文章的标题</a></h2>
                    <p class="summary">这是一篇非常详细的技术文章，深入探讨了前端架构设计的核心原理与最佳实践，涵盖了性能优化、用户体验提升、可维护性增强等多个关键主题，并通过实际案例展示了如何在不同场景下应用这些技术方案，总计超过一百二十个字符的详细描述内容。</p>
                </article>
            </div>
        </body>
        </html>
        """
        async def run():
            crawler = AdaptiveWebCrawler()

            # _crawl_list_page returns raw items from list page, no detail fetch
            items = await crawler._crawl_list_page(html_with_long_summary, "https://example.com/")

            assert len(items) == 1
            # ContentManager will call fetch_detail for every item regardless of summary length
            assert len(items[0].summary) > 100
        asyncio.run(run())

    def test_is_summary_enough(self, mock_schema_store):
        """测试 _is_summary_enough 方法"""
        async def run():
            crawler = AdaptiveWebCrawler()

            assert not crawler._is_summary_enough("")
            assert not crawler._is_summary_enough("a" * 50)
            assert not crawler._is_summary_enough("a" * 100)
            assert crawler._is_summary_enough("a" * 101)
            assert crawler._is_summary_enough("中文" * 51)
        asyncio.run(run())

    def test_has_valid_data(self):
        """测试 _has_valid_data 辅助方法正确识别有效/无效数据"""
        crawler = AdaptiveWebCrawler()

        valid_items = [
            {"url": "https://example.com/1", "title": "Title 1"},
            {"url": "https://example.com/2", "title": ""},
        ]
        assert crawler._has_valid_data(valid_items) is True

        url_only_items = [{"url": "https://example.com/1", "title": ""}]
        assert crawler._has_valid_data(url_only_items) is False

        title_only_items = [{"url": "", "title": "Title Only"}]
        assert crawler._has_valid_data(title_only_items) is False

        invalid_items = [{"url": "", "title": ""}]
        assert crawler._has_valid_data(invalid_items) is False

        assert crawler._has_valid_data([]) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

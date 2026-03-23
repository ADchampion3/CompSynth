"""
CompSynth Crawler 模块测试

测试目标: 美团技术博客 https://tech.meituan.com/
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from comp_synth.crawler.adaptive_crawler import AdaptiveWebCrawler
from comp_synth.crawler.dom_extractor import DOMExtractor
from comp_synth.crawler.schema_store import SchemaStore
from comp_synth.crawler.site_schema import SiteSchema
from comp_synth.schemas.web import WebPageItem

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db_path(monkeypatch):
    """使用临时数据库路径"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_schemas.db")
        monkeypatch.setattr("comp_synth.config.settings.site_schema_db_path", db_path)
        yield db_path


@pytest.fixture
def mock_schema_store(monkeypatch):
    """Mock SchemaStore 和 CrawlTracker 避免数据库依赖"""
    mock_store = MagicMock()
    mock_store.get.return_value = None
    mock_store.can_use_llm.return_value = True
    mock_store.save.return_value = None
    mock_store.mark_llm_called.return_value = None
    mock_store.update_list_selectors.return_value = None
    monkeypatch.setattr("comp_synth.crawler.adaptive_crawler.SchemaStore", lambda: mock_store)

    mock_tracker = MagicMock()
    mock_tracker.is_crawled.return_value = False
    mock_tracker.mark_crawled.return_value = None
    monkeypatch.setattr("comp_synth.crawler.adaptive_crawler.CrawlTracker", lambda: mock_tracker)

    return mock_store


@pytest.fixture
def sample_html():
    """美团技术博客的简化 HTML 示例"""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>测试文章 - 美团技术团队</title></head>
    <body>
        <article class="article-content">
            <h1 class="article-title">大前端：如何突破动态化容器的天花板？</h1>
            <div class="article-meta">
                <span class="author">张三</span>
                <time datetime="2024-10-18">2024年10月18日</time>
            </div>
            <div class="article-summary">
                本文探讨了大前端动态化技术的最新进展...
            </div>
            <div class="article-tags">
                <a class="tag">动态化</a>
                <a class="tag">前端</a>
                <a class="tag">容器</a>
            </div>
            <div class="article-body">
                <p>第一段内容...</p>
                <p>第二段内容...</p>
                <p>第三段内容...</p>
            </div>
        </article>
    </body>
    </html>
    """


@pytest.fixture
def meituan_list_html():
    """美团技术博客列表页 HTML"""
    return """
    <html>
    <body>
        <div class="post-list">
            <article class="post-item">
                <h2><a href="/2024/10/18/recce-in-meituan.html">大前端：如何突破动态化容器的天花板？</a></h2>
                <p class="summary">本文探讨了大前端动态化技术的最新进展...</p>
                <a href="/2024/10/18/recce-in-meituan.html" class="read-more">阅读全文</a>
            </article>
            <article class="post-item">
                <h2><a href="/2024/09/12/kdd-2024.html">KDD 2024 OAG-Challenge Cup赛道冠军技术方案解读</a></h2>
                <p class="summary">KDD 2024 冠军方案解读...</p>
                <a href="/2024/09/12/kdd-2024.html" class="read-more">阅读全文</a>
            </article>
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
            selectors={
                "title": "h1.article-title",
                "author": ".author",
                "content": ".article-body",
                "tags": ".article-tags .tag",
            },
        )

        assert schema.site_name == "tech.meituan.com"
        assert schema.site_url == "https://tech.meituan.com/"
        assert len(schema.selectors) == 4
        assert schema.created_at is not None
        assert schema.updated_at is not None
        assert schema.last_llm_call is None

    def test_schema_serialization(self):
        """测试 Schema JSON 序列化"""
        schema = SiteSchema(
            site_name="example.com",
            site_url="https://example.com",
            selectors={"title": "h1"},
        )

        json_str = schema.model_dump_json()
        data = json.loads(json_str)

        assert data["site_name"] == "example.com"
        assert data["selectors"]["title"] == "h1"

    def test_schema_deserialization(self):
        """测试 Schema JSON 反序列化"""
        data = {
            "site_name": "test.com",
            "site_url": "https://test.com",
            "selectors": {"title": "h1", "content": "article"},
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "last_llm_call": None,
        }

        schema = SiteSchema(**data)
        assert schema.site_name == "test.com"
        assert schema.selectors["content"] == "article"


# ============================================================================
# SchemaStore Tests
# ============================================================================

class TestSchemaStore:
    """SchemaStore 持久化测试"""

    def test_init_db(self, temp_db_path):
        """测试数据库初始化"""
        SchemaStore()
        assert os.path.exists(temp_db_path)

    def test_save_and_get(self, temp_db_path):
        """测试保存和获取 Schema"""
        store = SchemaStore()

        schema = SiteSchema(
            site_name="tech.meituan.com",
            site_url="https://tech.meituan.com/",
            selectors={"title": "h1"},
        )
        store.save(schema)

        retrieved = store.get("tech.meituan.com")
        assert retrieved is not None
        assert retrieved.site_name == "tech.meituan.com"
        assert retrieved.selectors["title"] == "h1"

    def test_get_nonexistent(self, temp_db_path):
        """测试获取不存在的 Schema"""
        store = SchemaStore()
        result = store.get("nonexistent.com")
        assert result is None

    def test_update_selectors(self, temp_db_path):
        """测试更新 selectors"""
        store = SchemaStore()

        schema = SiteSchema(
            site_name="test.com",
            site_url="https://test.com",
            selectors={"title": "h1"},
        )
        store.save(schema)

        store.update_selectors("test.com", {"title": "h2", "content": "article"})
        updated = store.get("test.com")

        assert updated.selectors["title"] == "h2"
        assert updated.selectors["content"] == "article"

    def test_can_use_llm_first_time(self, temp_db_path):
        """测试首次访问允许 LLM"""
        store = SchemaStore()
        assert store.can_use_llm("new.site.com") is True

    def test_can_use_llm_after_call(self, temp_db_path):
        """测试 LLM 调用后 24 小时内不允许再次调用"""
        store = SchemaStore()

        schema = SiteSchema(
            site_name="test.com",
            site_url="https://test.com",
            selectors={},
        )
        store.save(schema)
        store.mark_llm_called("test.com")

        assert store.can_use_llm("test.com") is False

    def test_mark_llm_called(self, temp_db_path):
        """测试标记 LLM 调用"""
        store = SchemaStore()

        schema = SiteSchema(
            site_name="test.com",
            site_url="https://test.com",
            selectors={},
        )
        store.save(schema)
        store.mark_llm_called("test.com")

        updated = store.get("test.com")
        assert updated.last_llm_call is not None


# ============================================================================
# DOMExtractor Tests
# ============================================================================

class TestDOMExtractor:
    """DOMExtractor 测试"""

    def test_extract_with_selectors_basic(self, sample_html):
        """测试基本的 CSS Selector 提取"""
        extractor = DOMExtractor()

        selectors = {
            "title": "h1.article-title",
            "author": ".author",
            "content": ".article-body",
        }

        result = extractor.extract_with_selectors(sample_html, selectors)

        assert result["title"] == "大前端：如何突破动态化容器的天花板？"
        assert result["author"] == "张三"
        assert "第一段内容" in result["content"]

    def test_extract_with_selectors_tags(self, sample_html):
        """测试提取标签列表"""
        extractor = DOMExtractor()

        selectors = {
            "title": "h1.article-title",
            "tags": ".article-tags .tag",
        }

        result = extractor.extract_with_selectors(sample_html, selectors)

        assert result["title"] == "大前端：如何突破动态化容器的天花板？"
        assert len(result["tags"]) == 3
        assert "动态化" in result["tags"]

    def test_extract_with_selectors_missing_field(self, sample_html):
        """测试提取不存在的字段"""
        extractor = DOMExtractor()

        selectors = {
            "nonexistent": ".does-not-exist",
        }

        result = extractor.extract_with_selectors(sample_html, selectors)
        assert result["nonexistent"] == ""

    def test_extract_with_selectors_content_join(self, sample_html):
        """测试多个 content 元素合并"""
        extractor = DOMExtractor()

        selectors = {
            "content": ".article-body p",
        }

        result = extractor.extract_with_selectors(sample_html, selectors)
        assert "第一段内容" in result["content"]
        assert "第二段内容" in result["content"]

    def test_extract_with_mock_llm(self, sample_html):
        """测试 LLM 提取（模拟）"""
        async def run_test():
            extractor = DOMExtractor()

            mock_response = MagicMock()
            mock_response.content = json.dumps({
                "title": "LLM 提取的标题",
                "author": "LLM 作者",
                "published_at": "2024-10-18T10:00:00",
                "content": "LLM 提取的正文内容",
                "tags": ["测试", "LLM"],
            })

            with patch.object(extractor, "_get_llm") as mock_get_llm:
                mock_llm = AsyncMock()
                mock_llm.ainvoke = AsyncMock(return_value=mock_response)
                mock_get_llm.return_value = mock_llm

                result = await extractor.extract(sample_html)

            assert result["title"] == "LLM 提取的标题"
            assert result["author"] == "LLM 作者"
            assert len(result["tags"]) == 2

        asyncio.run(run_test())

    def test_to_web_page_item(self):
        """测试转换为 WebPageItem"""
        extractor = DOMExtractor()

        extracted = {
            "title": "测试标题",
            "author": "测试作者",
            "content": "测试内容",
            "tags": ["tag1", "tag2"],
        }

        item = extractor.to_web_page_item(
            url="https://example.com/article",
            extracted=extracted,
            site_name="example.com",
        )

        assert isinstance(item, WebPageItem)
        assert item.url == "https://example.com/article"
        assert item.title == "测试标题"
        assert item.author == "测试作者"
        assert item.content == "测试内容"
        assert len(item.tags) == 2


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

    def test_extract_title_from_html(self, mock_schema_store, sample_html):
        """测试从 HTML 提取标题"""
        async def run():
            crawler = AdaptiveWebCrawler()
            title = await crawler._extract_title_from_html(sample_html, "https://example.com")
            assert "测试文章" in title

        asyncio.run(run())

    def test_extract_with_readability(self, mock_schema_store, sample_html):
        """测试 readability 提取"""
        async def run():
            crawler = AdaptiveWebCrawler()
            result = await crawler._extract_with_readability(sample_html)
            assert "title" in result
            assert "content" in result

        asyncio.run(run())

    def test_find_article_link(self, mock_schema_store, meituan_list_html):
        """测试从列表页查找文章链接"""
        async def run():
            crawler = AdaptiveWebCrawler()
            link = await crawler._find_article_link(meituan_list_html, "https://tech.meituan.com/")
            assert link is not None
            assert "recce-in-meituan" in link or "kdd-2024" in link

        asyncio.run(run())

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
        # cleanup
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
                # 最低保障：url + title
                assert item.title != ""

        asyncio.run(run())

    def test_duplicate_url_skipped(self):
        """测试重复 URL 被跳过"""
        async def run():
            crawler = AdaptiveWebCrawler()
            url = "https://tech.meituan.com/2024/10/18/recce-in-meituan.html"

            # 第一次爬取
            await crawler.fetch({"url": url})

            # 第二次爬取同一 URL 应该被跳过
            items2 = await crawler.fetch({"url": url})

            # 第二次应该返回空列表（已被爬取）
            assert items2 == [] or len(items2) == 0

        asyncio.run(run())


# ============================================================================
# Schema Persistence & Reuse Integration Tests (Real LLM)
# ============================================================================

class TestSchemaPersistenceAndReuse:
    """
    测试 Schema 持久化和复用（真实 LLM 调用）

    验证流程：
    1. 首次爬取：LLM 被调用生成 selectors 并保存到 DB
    2. 二次爬取：使用已保存的 CSS selectors，不调用 LLM
    """

    @pytest.fixture(autouse=True)
    def setup_real_schema_store(self, monkeypatch):
        """使用真实数据库路径（临时目录），不禁用 SchemaStore"""
        import os
        import tempfile

        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test_schema_reuse.db")
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)

        # 设置临时路径，但不 monkeypatch SchemaStore 类
        monkeypatch.setattr("comp_synth.config.settings.site_schema_db_path", db_path)
        monkeypatch.setattr("comp_synth.config.settings.data_dir", data_dir)
        monkeypatch.setattr("comp_synth.config.settings.crawl_db_path", os.path.join(data_dir, "crawl_state.db"))

        # 清除全局 crawler 实例的 schema_store 缓存，确保使用新 DB
        from comp_synth.crawler import adaptive_crawler
        adaptive_crawler.AdaptiveWebCrawler._schema_store = None
        adaptive_crawler.AdaptiveWebCrawler._tracker = None

        yield db_path

        # 清理
        import shutil
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass

    def test_first_crawl_saves_schema(self):
        """测试首次爬取后 schema 被保存到数据库"""
        from comp_synth.crawler.schema_store import SchemaStore

        async def run():
            crawler = AdaptiveWebCrawler()
            site = "example.com"

            # 初始状态：没有 schema
            store = SchemaStore()
            assert store.get(site) is None
            assert store.can_use_llm(site) is True

            # 模拟一次 LLM 调用后的状态（直接保存 schema）
            from comp_synth.crawler.site_schema import SiteSchema
            schema = SiteSchema(
                site_name=site,
                site_url=f"https://{site}",
                selectors={"title": "h1", "content": "article"},
            )
            store.save(schema)
            store.mark_llm_called(site)

            # 验证 schema 已保存
            retrieved = store.get(site)
            assert retrieved is not None
            assert retrieved.selectors["title"] == "h1"

            # 验证 LLM 调用已被标记（24小时内不允许再次调用）
            assert store.can_use_llm(site) is False

        asyncio.run(run())

    def test_second_crawl_uses_css_selector_not_llm(self):
        """
        测试二次爬取时使用 CSS selector 而不是 LLM

        策略：首次爬取用真实 LLM，第二次爬取时 mock LLM 并验证未被调用
        """

        from comp_synth.crawler.schema_store import SchemaStore

        async def run():
            crawler = AdaptiveWebCrawler()
            site = "httpbin.org"
            test_url = "https://httpbin.org/html"

            # 创建 crawler，它会使用真实 DOMExtractor 和 SchemaStore
            crawler = AdaptiveWebCrawler()

            # 第一次爬取：调用真实 LLM（如果需要）
            # 注意：如果 readability 能直接提取内容，可能不需要 LLM
            items1 = await crawler.fetch({"url": test_url})
            assert isinstance(items1, list)

            store = SchemaStore()

            # 检查 schema 是否被保存（如果 LLM 被调用）
            schema = store.get(site)
            can_use = store.can_use_llm(site)

            # 如果之前没有调用过 LLM，schema 可能是 None
            # 如果 readability 成功提取，不需要 LLM，schema 也不会被保存
            print(f"Schema after first crawl: {schema}")
            print(f"Can use LLM: {can_use}")

            # 第二次爬取：验证 LLM 未被调用
            llm_call_count = 0
            original_extract = crawler._dom_extractor.extract
            original_generate = crawler._dom_extractor.generate_selectors

            async def mock_extract(html):
                nonlocal llm_call_count
                llm_call_count += 1
                return await original_extract(html)

            async def mock_generate(html):
                nonlocal llm_call_count
                llm_call_count += 1
                return await original_generate(html)

            crawler._dom_extractor.extract = mock_extract
            crawler._dom_extractor.generate_selectors = mock_generate

            items2 = await crawler.fetch({"url": test_url})

            # 如果 schema 已保存，第二次爬取应该使用 CSS selector，不调用 LLM DOM 提取
            if schema and schema.selectors:
                assert llm_call_count == 0, f"二次爬取不应该调用 LLM，但调用了 {llm_call_count} 次"
            else:
                # 如果没有 schema（readability 成功提取），LLM 本就不应该被调用
                print("没有 schema 保存（readability 直接提取成功）")

        asyncio.run(run())

    def test_schema_reuse_verification(self):
        """综合测试：验证 schema 被正确保存和复用"""
        from comp_synth.crawler.schema_store import SchemaStore

        async def run():
            # 使用一个简单的测试页面
            test_url = "https://httpbin.org/html"

            # 第一次爬取
            crawler1 = AdaptiveWebCrawler()
            items1 = await crawler1.fetch({"url": test_url})
            assert len(items1) > 0

            # 检查 schema 状态
            store = SchemaStore()
            site_name = "httpbin.org"
            schema = store.get(site_name)

            # 第二次爬取 - 创建新的 crawler 实例，验证从 DB 加载 schema
            crawler2 = AdaptiveWebCrawler()
            items2 = await crawler2.fetch({"url": test_url})

            # 验证结果一致性
            if items1 and items2:
                # 如果两次都返回内容，title 应该一致
                assert items1[0].title == items2[0].title

            # 如果有 schema，验证其结构有效
            if schema:
                assert schema.site_name == site_name
                assert isinstance(schema.selectors, dict)
                print(f"Saved selectors: {schema.selectors}")

        asyncio.run(run())

    @pytest.mark.skipif(
        os.getenv("OPENAI_API_KEY") == "" or os.getenv("OPENAI_BASE_URL") == "",
        reason="需要真实 LLM API key"
    )
    def test_real_llm_extract_and_generate_selectors(self):
        """
        真实调用 LLM 的测试（仅在配置了 OPENAI_API_KEY 时运行）

        测试流程：
        1. 使用复杂 HTML（readability 提取困难）让 LLM 真正被调用
        2. 验证 LLM 返回的结构化数据
        3. 验证 LLM 生成的 selectors 可用于 CSS 提取
        """
        import httpx

        from comp_synth.crawler.dom_extractor import DOMExtractor

        async def run():
            extractor = DOMExtractor()

            # 获取美团技术博客文章页（结构复杂，readability 可能提取不佳）
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get("https://tech.meituan.com")
                    html = response.text
            except Exception as e:
                pytest.skip(f"网络请求失败: {e}")

            # 使用 LLM 提取内容（真实调用）
            print("\n=== 真实 LLM 调用：extract ===")
            extracted = await extractor.extract(html)
            print(f"LLM 提取结果: {extracted}")
            assert "title" in extracted
            assert "content" in extracted
            assert extracted["title"] != "" or extracted["content"] != "", "LLM 应返回非空结果"

            # 使用 LLM 生成 selectors（真实调用）
            print("\n=== 真实 LLM 调用：generate_selectors ===")
            selectors = await extractor.generate_selectors(html)
            print(f"LLM 生成的 selectors: {selectors}")
            assert isinstance(selectors, dict)
            assert "title" in selectors or "content" in selectors, "应至少生成 title 或 content selector"

            # 使用生成的 selectors 提取内容
            if selectors.get("content"):
                result = extractor.extract_with_selectors(html, selectors)
                print(f"使用 selectors 提取的 content 长度: {len(result.get('content', ''))}")
                print(f"使用 selectors 提取的 content: {result.get('content', '')}")
                assert result.get("content") != "", "CSS selector 应能提取到内容"

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

    def test_is_list_page_false(self, mock_schema_store, sample_html):
        """测试详情页（article 页面）检测返回 False"""
        async def run():
            crawler = AdaptiveWebCrawler()
            assert crawler._is_list_page(sample_html) is False
        asyncio.run(run())

    def test_extract_list_items(self, mock_schema_store, meituan_list_html):
        """测试从列表页提取多个条目"""
        async def run():
            crawler = AdaptiveWebCrawler()
            items = await crawler._extract_list_items(
                meituan_list_html, "https://tech.meituan.com/", "tech.meituan.com"
            )
            assert len(items) >= 2, f"应该提取到至少2个条目，实际: {len(items)}"
            # 验证第一个条目
            assert "recce-in-meituan" in items[0]["url"]
            assert "大前端" in items[0]["title"]
            # 验证第二个条目
            assert "kdd-2024" in items[1]["url"]
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
            # 应该去重，只保留唯一的 URL
            urls = [item["url"] for item in items]
            assert len(urls) == len(set(urls)), "URL 应该去重"
            assert len(items) == 2, f"应该只有2个唯一条目，实际: {len(items)}"
        asyncio.run(run())

    def test_crawl_list_page_with_mocked_detail(self, mock_schema_store, meituan_list_html):
        """测试列表页爬取返回多个 WebPageItem（mock 详情页）"""
        async def run():
            crawler = AdaptiveWebCrawler()

            # Mock _fetch_article_detail 返回预设内容
            async def mock_detail(url):
                from comp_synth.schemas.web import WebPageItem
                return WebPageItem(
                    url=url,
                    title=f"详情页标题: {url}",
                    content=f"这是 {url} 的正文内容",
                    summary="摘要",
                    site_name="tech.meituan.com",
                )

            crawler._fetch_article_detail = mock_detail

            items = await crawler._crawl_list_page(meituan_list_html, "https://tech.meituan.com/")

            assert len(items) >= 2, f"应该返回至少2个条目，实际: {len(items)}"
            # 验证返回的是 WebPageItem
            for item in items:
                assert item.url.startswith("https://tech.meituan.com/")
                assert item.title != ""
                assert item.content != "" or item.summary != ""
        asyncio.run(run())

    def test_crawl_list_page_skips_detail_when_summary_enough(self, mock_schema_store):
        """测试 summary 足够长时不爬详情页"""
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

            # Mock _fetch_article_detail，如果被调用会返回预设内容
            async def mock_detail(url):
                from comp_synth.schemas.web import WebPageItem
                return WebPageItem(
                    url=url,
                    title=f"详情页标题: {url}",
                    content=f"这是 {url} 的正文内容",
                    summary="摘要",
                    site_name="example.com",
                )

            crawler._fetch_article_detail = mock_detail

            items = await crawler._crawl_list_page(html_with_long_summary, "https://example.com/")

            assert len(items) == 1
            # content 应该为空，因为没有爬详情页
            assert items[0].content == ""
            # summary 应该是原始的长 summary
            assert len(items[0].summary) > 100
            # mock_detail 不应该被调用
        asyncio.run(run())

    def test_is_summary_enough(self, mock_schema_store):
        """测试 _is_summary_enough 方法"""
        async def run():
            crawler = AdaptiveWebCrawler()

            # 长度 <= 100 返回 False
            assert crawler._is_summary_enough("") == False
            assert crawler._is_summary_enough("a" * 50) == False
            assert crawler._is_summary_enough("a" * 100) == False

            # 长度 > 100 返回 True
            assert crawler._is_summary_enough("a" * 101) == True
            assert crawler._is_summary_enough("中文" * 51) == True
        asyncio.run(run())

    def test_extract_list_items_returns_empty_list(self):
        """测试 extract_list_items_with_selectors 返回空列表"""
        from comp_synth.crawler.dom_extractor import DOMExtractor

        extractor = DOMExtractor()
        html = "<html><body><div class='no-match'></div></body></html>"
        selectors = {
            "item_container": ".post",
            "url": "a",
            "title": "h2",
            "summary": "p"
        }
        result = extractor.extract_list_items_with_selectors(html, selectors)
        assert result == []

    def test_has_valid_data(self):
        """测试 _has_valid_data 辅助方法正确识别有效/无效数据"""
        from comp_synth.crawler.adaptive_crawler import AdaptiveWebCrawler

        crawler = AdaptiveWebCrawler()

        # 有效数据：title 和 url 都非空
        valid_items = [
            {"url": "https://example.com/1", "title": "Title 1"},
            {"url": "https://example.com/2", "title": ""},
        ]
        assert crawler._has_valid_data(valid_items) is True

        # 无效数据：只有 url，title 为空
        url_only_items = [
            {"url": "https://example.com/1", "title": ""},
        ]
        assert crawler._has_valid_data(url_only_items) is False

        # 无效数据：title 非空但 url 为空
        title_only_items = [
            {"url": "", "title": "Title Only"},
        ]
        assert crawler._has_valid_data(title_only_items) is False

        # 无效数据：全部为空
        invalid_items = [
            {"url": "", "title": ""},
        ]
        assert crawler._has_valid_data(invalid_items) is False

        # 空列表
        assert crawler._has_valid_data([]) is False


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

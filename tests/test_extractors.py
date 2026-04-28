"""
CompSynth Extractors 模块测试
"""


from comp_synth.crawlers.extractors import DOMExtractor, ListItemSelector


class TestListItemSelector:
    """ListItemSelector 模型测试"""

    def test_list_item_selector_has_time_field(self):
        """测试 ListItemSelector 包含 time 字段"""
        selector = ListItemSelector(
            item_container="article",
            url="a",
            title="h2",
            summary="p",
            time="time"
        )
        assert hasattr(selector, "time")
        assert selector.time == "time"

    def test_list_item_selector_time_default_empty(self):
        """测试 time 字段默认为空字符串"""
        selector = ListItemSelector(
            item_container="article",
            url="a",
            title="h2",
            summary="p",
        )
        assert selector.time == ""


class TestExtractListItemsWithTime:
    """测试 extract_list_items_with_selectors 的时间提取功能"""

    def test_extract_list_items_with_time_datetime_attr(self):
        """测试从 time 元素的 datetime 属性提取时间"""
        html = """
        <html><body>
        <div class="post-list">
            <article>
                <a href="/2026/04/10/article1.html">
                    <h2>文章标题1</h2>
                </a>
                <time datetime="2026-04-10">2026-04-10</time>
                <p>摘要1</p>
            </article>
            <article>
                <a href="/2026/04/08/article2.html">
                    <h2>文章标题2</h2>
                </a>
                <time datetime="2026-04-08">2026-04-08</time>
                <p>摘要2</p>
            </article>
        </div>
        </body></html>
        """
        extractor = DOMExtractor()
        selectors = [{
            "item_container": "article",
            "url": "a",
            "title": "h2",
            "summary": "p",
            "time": "time"
        }]
        items = extractor.extract_list_items_with_selectors(html, selectors)
        assert len(items) == 2
        # 验证 published_at 字段存在
        assert all("published_at" in item for item in items)
        # 验证时间被正确提取
        assert items[0]["published_at"] is not None
        assert items[1]["published_at"] is not None

    def test_extract_list_items_with_time_text(self):
        """测试从 time 元素的文本内容提取时间"""
        html = """
        <html><body>
        <div class="post-list">
            <article>
                <a href="/2026/04/10/article1.html">
                    <h2>文章标题1</h2>
                </a>
                <span class="date">2026-04-10</span>
                <p>摘要1</p>
            </article>
        </div>
        </body></html>
        """
        extractor = DOMExtractor()
        selectors = [{
            "item_container": "article",
            "url": "a",
            "title": "h2",
            "summary": "p",
            "time": "span.date"
        }]
        items = extractor.extract_list_items_with_selectors(html, selectors)
        assert len(items) == 1
        assert items[0]["published_at"] is not None
        assert items[0]["published_at"].year == 2026
        assert items[0]["published_at"].month == 4
        assert items[0]["published_at"].day == 10

    def test_extract_list_items_without_time_selector(self):
        """测试不提供 time selector 时 published_at 为 None"""
        html = """
        <html><body>
        <div class="post-list">
            <article>
                <a href="/article1.html">
                    <h2>文章标题1</h2>
                </a>
                <p>摘要1</p>
            </article>
        </div>
        </body></html>
        """
        extractor = DOMExtractor()
        selectors = [{
            "item_container": "article",
            "url": "a",
            "title": "h2",
            "summary": "p",
        }]
        items = extractor.extract_list_items_with_selectors(html, selectors)
        assert len(items) == 1
        assert items[0]["published_at"] is None

    def test_extract_list_items_mixed_time_and_no_time(self):
        """测试混合场景：部分容器有时间，部分没有"""
        html = """
        <html><body>
        <div class="post-list">
            <article>
                <a href="/2026/04/10/article1.html">
                    <h2>文章标题1</h2>
                </a>
                <time datetime="2026-04-10">2026-04-10</time>
                <p>摘要1</p>
            </article>
            <article>
                <a href="/article2.html">
                    <h2>文章标题2</h2>
                </a>
                <p>摘要2</p>
            </article>
        </div>
        </body></html>
        """
        extractor = DOMExtractor()
        selectors = [{
            "item_container": "article",
            "url": "a",
            "title": "h2",
            "summary": "p",
            "time": "time"
        }]
        items = extractor.extract_list_items_with_selectors(html, selectors)
        assert len(items) == 2
        # 第一篇有时间
        assert items[0]["published_at"] is not None
        # 第二篇无时间
        assert items[1]["published_at"] is None

"""
CompSynth Extractors 模块测试
"""

import os

from bs4 import BeautifulSoup

from comp_synth.crawlers.extractors import DOMExtractor, ListItemSelector

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "html")


def load_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES_DIR, name), encoding="utf-8") as f:
        return f.read()


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


class TestDeepClean:
    """Test _deep_clean: content noise removal"""

    def _clean(self, html: str) -> BeautifulSoup:
        soup = BeautifulSoup(html, "html.parser")
        return DOMExtractor()._deep_clean(soup)

    def test_removes_cookie_consent(self):
        html = '<div class="cookie-notice"><p>Cookies</p></div><div class="content">ok</div>'
        soup = self._clean(html)
        assert soup.find(class_="cookie-notice") is None
        assert soup.find(class_="content") is not None

    def test_removes_gdpr_consent(self):
        html = '<div class="gdpr-consent"><p>GDPR</p></div><p>body</p>'
        soup = self._clean(html)
        assert soup.find(class_="gdpr-consent") is None

    def test_removes_ads(self):
        html = '<div class="ad-banner">ad</div><div class="advertisement">ad2</div><div class="google-ad">ad3</div><div class="sponsor">ad4</div><p>content</p>'
        soup = self._clean(html)
        assert soup.find(class_="ad-banner") is None
        assert soup.find(class_="advertisement") is None
        assert soup.find(class_="google-ad") is None
        assert soup.find(class_="sponsor") is None

    def test_removes_social_sharing(self):
        html = '<div class="share-buttons">share</div><div class="social-share">social</div><div class="addtoany">a2a</div><p>content</p>'
        soup = self._clean(html)
        assert soup.find(class_="share-buttons") is None
        assert soup.find(class_="social-share") is None
        assert soup.find(class_="addtoany") is None

    def test_removes_comments_section(self):
        html = '<section id="comments"><p>comment</p></section><div class="comment-respond"><form></form></div><p>content</p>'
        soup = self._clean(html)
        assert soup.find(id="comments") is None
        assert soup.find(class_="comment-respond") is None

    def test_removes_related_posts(self):
        html = '<div class="related-posts">related</div><div class="recommend-read">rec</div><p>content</p>'
        soup = self._clean(html)
        assert soup.find(class_="related-posts") is None
        assert soup.find(class_="recommend-read") is None

    def test_removes_pagination(self):
        html = '<div class="pagination"><a>1</a><a>2</a></div><nav class="pager"><a>next</a></nav><p>content</p>'
        soup = self._clean(html)
        assert soup.find(class_="pagination") is None
        assert soup.find(class_="pager") is None

    def test_removes_breadcrumbs(self):
        html = '<div class="breadcrumbs"><a>Home</a></div><div class="breadcrumb"><a>Home</a></div><p>content</p>'
        soup = self._clean(html)
        assert soup.find(class_="breadcrumbs") is None
        assert soup.find(class_="breadcrumb") is None

    def test_removes_sidebar(self):
        html = '<aside class="sidebar">sidebar</aside><div class="widget">widget</div><p>content</p>'
        soup = self._clean(html)
        assert soup.find("aside") is None
        assert soup.find(class_="widget") is None

    def test_removes_hidden_elements(self):
        html = '<div hidden>h1</div><div style="display:none">h2</div><div aria-hidden="true">h3</div><p>visible</p>'
        soup = self._clean(html)
        assert soup.find("div", attrs={"hidden": True}) is None
        assert soup.find(attrs={"aria-hidden": "true"}) is None
        assert soup.find("p") is not None

    def test_removes_search_forms(self):
        html = '<div class="search-widget"><form><input></form></div><div class="newsletter-signup"><form></form></div><p>content</p>'
        soup = self._clean(html)
        assert soup.find(class_="search-widget") is None
        assert soup.find(class_="newsletter-signup") is None

    def test_preserves_article_content(self):
        html = load_fixture("blog_list.html")
        soup = self._clean(html)
        articles = soup.find_all("article", class_="post-item")
        assert len(articles) == 3
        # Titles preserved
        titles = [a.find("h2").get_text() for a in articles]
        assert "Python 异步编程最佳实践 2026" in titles[0]

    def test_removes_noise_from_fixture(self):
        html = load_fixture("noise_heavy.html")
        soup = self._clean(html)
        # No cookie, ads, sidebar, comments, related, pagination
        assert soup.find(class_="cookie-banner") is None
        assert soup.find(class_="ad-header") is None
        assert soup.find(class_="sidebar") is None
        assert soup.find(id="comments") is None

    def test_does_not_remove_classes_with_ad_mid_word(self):
        """ArticleList-module-... should NOT be removed as an 'ad' pattern"""
        html = '<article class="ArticleList-module-scss-module__tPU-a__article"><h2>Title</h2></article>'
        soup = self._clean(html)
        assert soup.find("article") is not None
        assert soup.find("h2").get_text() == "Title"


class TestStripAttributes:
    """Test _strip_attributes: attribute stripping with URL normalization"""

    def _strip(self, html: str) -> BeautifulSoup:
        soup = BeautifulSoup(html, "html.parser")
        return DOMExtractor()._strip_attributes(soup)

    def test_removes_style_attribute(self):
        html = '<div style="color:red" class="test">text</div>'
        soup = self._strip(html)
        assert soup.find("div").get("style") is None
        assert soup.find("div").get("class") == ["test"]

    def test_removes_dimension_attributes(self):
        html = '<table width="100" height="50" border="1" cellpadding="5" cellspacing="0"><tr><td>cell</td></tr></table>'
        soup = self._strip(html)
        td = soup.find("table")
        assert td.get("width") is None
        assert td.get("height") is None
        assert td.get("border") is None
        assert td.get("cellpadding") is None
        assert td.get("cellspacing") is None

    def test_removes_interactive_attributes(self):
        html = '<div tabindex="0" draggable="true" contenteditable="true">text</div>'
        soup = self._strip(html)
        div = soup.find("div")
        assert div.get("tabindex") is None
        assert div.get("draggable") is None
        assert div.get("contenteditable") is None

    def test_removes_anchor_target_rel(self):
        html = '<a href="/page" target="_blank" rel="noopener">link</a>'
        soup = self._strip(html)
        a = soup.find("a")
        assert a.get("href") == "/page"
        assert a.get("target") is None
        assert a.get("rel") is None

    def test_keeps_role_and_aria(self):
        html = '<div role="main" aria-label="content">text</div>'
        soup = self._strip(html)
        div = soup.find("div")
        assert div.get("role") == "main"
        assert div.get("aria-label") == "content"

    def test_keeps_class_id_href_src_datetime(self):
        html = '<article class="post" id="p1"><a href="/link"><img src="/img.jpg"></a><time datetime="2026-05-01">date</time></article>'
        soup = self._strip(html)
        art = soup.find("article")
        assert art.get("class") == ["post"]
        assert art.get("id") == "p1"
        assert soup.find("a").get("href") == "/link"
        assert soup.find("img").get("src") == "/img.jpg"
        assert soup.find("time").get("datetime") == "2026-05-01"

    def test_strips_utm_params_from_href(self):
        html = '<a href="/page?utm_source=feed&utm_medium=rss&key=val">link</a>'
        soup = self._strip(html)
        href = soup.find("a").get("href")
        assert "utm_source" not in href
        assert "utm_medium" not in href
        assert "key=val" in href

    def test_strips_fbclid_from_href(self):
        html = '<a href="/page?fbclid=abc123&key=val">link</a>'
        soup = self._strip(html)
        href = soup.find("a").get("href")
        assert "fbclid" not in href
        assert "key=val" in href

    def test_strips_ref_source_spm_from_href(self):
        html = '<a href="/page?ref=sidebar&source=feed&spm=123&from=home">link</a>'
        soup = self._strip(html)
        href = soup.find("a").get("href")
        assert "ref=" not in href
        assert "source=" not in href
        assert "spm=" not in href
        assert "from=" not in href

    def test_handles_href_without_query(self):
        html = '<a href="/simple-path">link</a>'
        soup = self._strip(html)
        assert soup.find("a").get("href") == "/simple-path"


class TestExtractListItems:
    """测试 extract_list_items_with_selectors 的基本功能"""

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

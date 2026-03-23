import asyncio
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from readability import Document

from comp_synth.config import settings
from comp_synth.crawler.base import BaseCrawler
from comp_synth.crawler.dom_extractor import DOMExtractor
from comp_synth.crawler.schema_store import SchemaStore
from comp_synth.schemas.web import WebPageItem
from comp_synth.store.crawl_tracker import CrawlTracker


class AdaptiveWebCrawler(BaseCrawler):
    """
    自适应网页爬虫，灵活应对非标准博客结构。

    最低保障：url + title
    content 获取策略：
        1. readability 直接提取
        2. CSS Selector 提取（已有 Schema）
        3. 二次爬取（从列表页 follow 到详情页获取完整内容）
        4. LLM 提取（仅在允许时，每站每天 1 次）
    """

    def __init__(self):
        self._schema_store = SchemaStore()
        self._dom_extractor = DOMExtractor()
        self._tracker = CrawlTracker()

    def _detect_site(self, url: str) -> str:
        """根据 URL 检测站点名称（使用域名）"""
        parsed = urlparse(url)
        return parsed.netloc or "unknown"

    async def _fetch_html(self, url: str) -> str:
        """获取网页 HTML"""
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    async def _extract_title_from_html(self, html: str, url: str) -> str:
        """从 HTML 中提取标题（基础方法，不依赖 readability）"""
        soup = BeautifulSoup(html, "html.parser")

        # 尝试 <title> 标签
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)

        # 尝试 h1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        return url

    async def _extract_with_readability(self, html: str) -> dict[str, str]:
        """使用 readability-lxml 提取正文，返回 {title, content, summary}"""
        try:
            doc = Document(html)
            title = doc.short_title() or ""
            summary = doc.summary() or ""

            # 解析 summary 中的 HTML，提取纯文本
            if summary:
                soup = BeautifulSoup(summary, "html.parser")
                summary_text = soup.get_text(separator="\n", strip=True)
            else:
                summary_text = ""

            # 提取正文内容
            content_html = doc.content() or ""
            if content_html:
                soup = BeautifulSoup(content_html, "html.parser")
                content_text = soup.get_text(separator="\n", strip=True)
            else:
                content_text = ""

            return {
                "title": title,
                "content": content_text,
                "summary": summary_text,
            }
        except Exception as e:
            logger.warning(f"readability 提取失败: {e}")
            return {"title": "", "content": "", "summary": ""}

    async def _extract_with_schema(self, html: str, selectors: dict[str, str]) -> dict[str, str]:
        """使用 CSS Selector 直接提取"""
        try:
            return self._dom_extractor.extract_with_selectors(html, selectors)
        except Exception as e:
            logger.warning(f"CSS Selector 提取失败: {e}")
            return {"title": "", "author": "", "published_at": "", "content": "", "tags": []}

    async def _find_article_link(self, html: str, current_url: str) -> str | None:
        """
        从列表页/索引页找到文章详情页链接。
        适用于列表页 -> 详情页的二次爬取场景。
        """
        soup = BeautifulSoup(html, "html.parser")

        # 查找文章链接：常见模式
        article_link = None

        # 1. 查找 <article> 内的链接
        article = soup.find("article")
        if article:
            link = article.find("a", href=True)
            if link:
                article_link = link["href"]

        # 2. 查找标题链接（h1, h2, h3 附近的链接）
        if not article_link:
            for tag in soup.find_all(["h1", "h2", "h3"], class_=True):
                parent = tag.find_parent()
                if parent:
                    link = parent.find("a", href=True)
                    if link:
                        article_link = link["href"]
                        break

        # 3. 查找常见的文章链接模式
        if not article_link:
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True)
                if text and len(text) > 20:  # 假设文章标题较长
                    href = a["href"]
                    if href.startswith("http") or href.startswith("/"):
                        article_link = href
                        break

        if article_link:
            # 转为绝对 URL
            return urljoin(current_url, article_link)
        return None

    async def _learn_and_extract(self, html: str, site_name: str) -> dict[str, str]:
        """首次访问站点：使用 LLM 学习并提取"""
        try:
            # 并发调用：生成 selectors 和提取内容
            selectors_task = self._dom_extractor.generate_selectors(html)
            extract_task = self._dom_extractor.extract(html)

            selectors, extracted = await asyncio.gather(selectors_task, extract_task)

            if selectors:
                # 保存 schema
                from comp_synth.crawler.site_schema import SiteSchema

                schema = SiteSchema(
                    site_name=site_name,
                    site_url=f"https://{site_name}",
                    selectors=selectors,
                )
                self._schema_store.save(schema)
                logger.info(f"站点 {site_name} 的 Schema 已保存")

            # 标记 LLM 已调用
            self._schema_store.mark_llm_called(site_name)

            return extracted
        except Exception as e:
            logger.error(f"LLM 学习提取失败: {e}")
            return {"title": "", "author": "", "published_at": "", "content": "", "tags": []}

    def _build_item(
        self,
        url: str,
        title: str = "",
        content: str = "",
        summary: str = "",
        author: str = "",
        tags: list[str] | None = None,
        site_name: str = "",
    ) -> WebPageItem:
        """构建 WebPageItem，最低保障 url + title"""
        return WebPageItem(
            url=url,
            title=title or url,  # title 最低保障为 url
            content=content,
            summary=summary,
            author=author,
            tags=tags or [],
            site_name=site_name or self._detect_site(url),
        )

    async def fetch(self, source_config: dict) -> list[WebPageItem]:
        """
        自适应爬取流程：
        1. 获取 HTML
        2. 尝试 readability 提取（url + title 最低保障）
        3. content 提取失败时尝试 Schema
        4. Schema 失败时尝试二次爬取（跟随文章链接）
        5. 最终尝试 LLM 提取
        """
        url = source_config["url"]
        site_name = self._detect_site(url)

        # 检查是否已爬取过该 URL
        if self._tracker.is_crawled("web", url):
            logger.info(f"URL 已爬取，跳过: {url}")
            return []

        try:
            html = await self._fetch_html(url)
        except Exception as e:
            logger.error(f"获取网页失败 {url}: {e}")
            return []

        item: WebPageItem | None = None
        schema = self._schema_store.get(site_name)

        # === 步骤 1：readability 提取 ===
        readability_result = await self._extract_with_readability(html)
        has_content = bool(readability_result.get("content") and len(readability_result["content"]) > 100)

        if has_content:
            item = self._build_item(
                url=url,
                title=readability_result.get("title", ""),
                content=readability_result.get("content", ""),
                summary=readability_result.get("summary", ""),
                site_name=site_name,
            )
            self._tracker.mark_crawled("web", url)
            return [item]

        # === 步骤 2：尝试 Schema (CSS Selector) ===
        if schema and schema.selectors:
            schema_result = await self._extract_with_schema(html, schema.selectors)
            if schema_result.get("content"):
                item = self._build_item(
                    url=url,
                    title=schema_result.get("title", "") or readability_result.get("title", ""),
                    content=schema_result.get("content", ""),
                    author=schema_result.get("author", ""),
                    tags=schema_result.get("tags", []),
                    site_name=site_name,
                )
                self._tracker.mark_crawled("web", url)
                return [item]

        # === 步骤 3：二次爬取 ===
        # content 无法直接获取，尝试 follow 到详情页
        article_link = await self._find_article_link(html, url)
        if article_link and article_link != url:
            try:
                logger.info(f"二次爬取获取完整内容: {article_link}")
                detail_html = await self._fetch_html(article_link)
                detail_result = await self._extract_with_readability(detail_html)

                if detail_result.get("content"):
                    item = self._build_item(
                        url=url,  # 保持原始 URL
                        title=readability_result.get("title", "") or detail_result.get("title", ""),
                        content=detail_result.get("content", ""),
                        summary=detail_result.get("summary", ""),
                        site_name=site_name,
                    )
                    self._tracker.mark_crawled("web", url)
                    return [item]
            except Exception as e:
                logger.warning(f"二次爬取失败: {e}")

        # === 步骤 4：LLM 提取（每站每天 1 次）===
        if self._schema_store.can_use_llm(site_name):
            llm_result = await self._learn_and_extract(html, site_name)
            if llm_result.get("content") or llm_result.get("title"):
                item = self._build_item(
                    url=url,
                    title=llm_result.get("title", "") or readability_result.get("title", ""),
                    content=llm_result.get("content", ""),
                    author=llm_result.get("author", ""),
                    tags=llm_result.get("tags", []),
                    site_name=site_name,
                )
                self._tracker.mark_crawled("web", url)
                return [item]

        # === 最终保底：返回最低信息（url + title）===
        item = self._build_item(
            url=url,
            title=readability_result.get("title", "") or url,
            content="",
            summary=readability_result.get("summary", ""),
            site_name=site_name,
        )
        self._tracker.mark_crawled("web", url)
        return [item]

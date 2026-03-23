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

    def _is_list_page(self, html: str) -> bool:
        """
        检测页面是否为列表页（包含多个文章链接）
        """
        soup = BeautifulSoup(html, "html.parser")

        # 策略1：查找 article 容器
        article = soup.find("article")
        if article:
            links = article.find_all("a", href=True)
            if len(links) > 1:
                return True

        # 策略2：查找多个 h2/h3 链接
        headings = soup.find_all(["h2", "h3"], class_=True)
        heading_links = 0
        for h in headings:
            if h.find("a", href=True):
                heading_links += 1
        if heading_links > 1:
            return True

        # 策略3：查找常见的列表容器
        for container_selector in [".post-list", ".article-list", ".entries", "main"]:
            container = soup.select_one(container_selector)
            if container:
                links = container.find_all("a", href=True)
                if len(links) > 2:
                    return True

        return False

    def _has_valid_data(self, items: list[dict]) -> bool:
        """检查是否有有效数据（至少 title 和 url 非空）"""
        return any(item.get("title") and item.get("url") for item in items)

    async def _extract_list_items(
        self,
        html: str,
        base_url: str,
        site_name: str,
        user_selectors: dict = None,
    ) -> list[dict]:
        """
        从列表页提取所有文章条目，返回 [{"url": "", "title": "", "summary": ""}, ...]

        提取策略（优先级从高到低）：
        1. 用户配置的 selectors
        2. DB 中已存储的 list_selectors
        3. LLM 学习并提取
        4. 启发式后备方案
        """
        # 步骤1：尝试用户配置的 selectors
        if user_selectors:
            items = self._dom_extractor.extract_list_items_with_selectors(html, user_selectors)
            if items and self._has_valid_data(items):
                logger.info("使用用户配置的 selectors 提取列表项")
                # 转换为绝对 URL
                for item in items:
                    if item.get("url"):
                        item["url"] = urljoin(base_url, item["url"])
                return self._deduplicate_items(items)

        # 步骤2：DB selectors
        schema = self._schema_store.get(site_name)
        if schema and schema.list_selectors:
            items = self._dom_extractor.extract_list_items_with_selectors(html, schema.list_selectors)
            if items and self._has_valid_data(items):
                logger.info("使用 DB 的 list_selectors 提取列表项")
                for item in items:
                    if item.get("url"):
                        item["url"] = urljoin(base_url, item["url"])
                return self._deduplicate_items(items)

        # 步骤3：LLM 学习
        if self._schema_store.can_use_llm(site_name):
            llm_items = await self._learn_list_item_schema(html, site_name)
            if llm_items:
                for item in llm_items:
                    if item.get("url"):
                        item["url"] = urljoin(base_url, item["url"])
                return self._deduplicate_items(llm_items)

        # 步骤4：启发式后备
        logger.info("使用启发式方法提取列表项")
        return await self._extract_list_items_heuristic(html, base_url)

    async def _learn_list_item_schema(self, html: str, site_name: str) -> list[dict]:
        """使用 LLM 学习列表页结构并提取文章条目"""
        try:
            # 并发调用：生成 list selectors 和提取内容
            selectors_task = self._dom_extractor.generate_list_item_selectors(html)
            extract_task = self._dom_extractor.extract_list_items(html)

            list_selectors, extracted = await asyncio.gather(selectors_task, extract_task)

            items = extracted.get("items", [])

            if list_selectors and items:
                # 保存 list_selectors 到 schema
                self._schema_store.update_list_selectors(site_name, list_selectors)
                logger.info(f"站点 {site_name} 的 list_selectors 已保存: {list_selectors}")

            # 标记 LLM 已调用
            self._schema_store.mark_llm_called(site_name)

            return items
        except Exception as e:
            logger.error(f"LLM 学习列表页结构失败: {e}")
            return []

    async def _extract_list_items_heuristic(self, html: str, base_url: str) -> list[dict]:
        """
        使用启发式方法从列表页提取所有文章条目（后备方案）
        """
        soup = BeautifulSoup(html, "html.parser")
        items = []

        # 策略1：查找列表容器，然后查找容器内的 article 或 .post-item 条目
        for container_selector in [".post-list", ".article-list", ".entries", "main", "article"]:
            container = soup.select_one(container_selector)
            if container:
                # 使用 CSS 选择器查找 article 条目
                article_items = container.select("article.post-item, article[class*='post'], div.post-item, div[class*='post']")

                # 如果没有找到，尝试查找所有 article 作为后备
                if not article_items:
                    article_items = container.find_all("article")

                for item in article_items:
                    link = item.find("a", href=True)
                    if link:
                        title = link.get_text(strip=True)
                        href = link["href"]
                        # 查找摘要
                        summary_elem = item.find(class_=lambda c: c and "summary" in c.lower())
                        summary = summary_elem.get_text(strip=True) if summary_elem else ""
                        if title and len(title) > 5:
                            items.append({
                                "url": urljoin(base_url, href),
                                "title": title,
                                "summary": summary,
                            })
                if items:
                    break

        # 策略2：从 h2/h3 附近的链接提取
        if not items:
            for tag in soup.find_all(["h2", "h3"], class_=True):
                link = tag.find("a", href=True)
                if link:
                    title = link.get_text(strip=True)
                    if len(title) > 10:
                        # 查找同级附近的 summary
                        summary = ""
                        sibling = tag.find_next_sibling()
                        if sibling:
                            summary_elem = sibling.find(class_=lambda c: c and "summary" in c.lower())
                            if summary_elem:
                                summary = summary_elem.get_text(strip=True)
                        items.append({
                            "url": urljoin(base_url, link["href"]),
                            "title": title,
                            "summary": summary,
                        })

        return self._deduplicate_items(items)

    def _deduplicate_items(self, items: list[dict]) -> list[dict]:
        """基于 URL 去重"""
        seen_urls = set()
        unique_items = []
        for item in items:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                unique_items.append(item)
        return unique_items

    async def _fetch_article_detail(self, url: str) -> WebPageItem | None:
        """
        获取文章详情页内容（使用现有提取逻辑）
        """
        try:
            html = await self._fetch_html(url)
            result = await self._extract_with_readability(html)
            if result.get("content"):
                return self._build_item(
                    url=url,
                    title=result.get("title", ""),
                    content=result.get("content", ""),
                    summary=result.get("summary", ""),
                    site_name=self._detect_site(url),
                )
        except Exception as e:
            logger.warning(f"详情页爬取失败 {url}: {e}")
        return None

    def _is_summary_enough(self, summary: str) -> bool:
        """判断 summary 是否足够（不为空且长度 > 100）"""
        return bool(summary and len(summary) > 100)

    async def _crawl_list_page(self, html: str, url: str, user_selectors: dict = None) -> list[WebPageItem]:
        """
        爬取列表页，提取所有文章条目
        核心原则：只有 summary 缺失或太短时才爬详情页
        """
        site_name = self._detect_site(url)
        items = await self._extract_list_items(html, url, site_name)
        results = []

        for item_dict in items:
            # 检查是否已爬取
            if self._tracker.is_crawled("web", item_dict["url"]):
                logger.info(f"列表中 URL 已爬取，跳过: {item_dict['url']}")
                continue

            item_summary = item_dict.get("summary", "")

            # 只有 summary 缺失或太短时才爬详情页
            if not self._is_summary_enough(item_summary):
                logger.info(f"Summary 不足，爬取详情页: {item_dict['url']}")
                detail_item = await self._fetch_article_detail(item_dict["url"])
                if detail_item:
                    results.append(detail_item)
                    self._tracker.mark_crawled("web", item_dict["url"])
            else:
                # 直接使用列表页提取的元数据，不爬详情页
                item = self._build_item(
                    url=item_dict["url"],
                    title=item_dict.get("title", ""),
                    content="",  # 订阅场景不需要完整 content
                    summary=item_summary,
                    site_name=self._detect_site(item_dict["url"]),
                )
                results.append(item)
                self._tracker.mark_crawled("web", item_dict["url"])

        # 标记列表页本身已爬取
        self._tracker.mark_crawled("web", url)

        return results

    async def _crawl_detail_page(self, html: str, url: str, user_selectors: dict = None) -> list[WebPageItem]:
        """
        爬取详情页（原有逻辑）
        """
        site_name = self._detect_site(url)
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
        article_link = await self._find_article_link(html, url)
        if article_link and article_link != url:
            try:
                logger.info(f"二次爬取获取完整内容: {article_link}")
                detail_html = await self._fetch_html(article_link)
                detail_result = await self._extract_with_readability(detail_html)

                if detail_result.get("content"):
                    item = self._build_item(
                        url=url,
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

    async def fetch(self, source_config: dict, user_selectors: dict = None) -> list[WebPageItem]:
        """
        自适应爬取流程：
        1. 获取 HTML
        2. 检测页面类型：列表页 vs 详情页
        3. 列表页：提取所有文章条目并 follow 获取详情
        4. 详情页：使用现有逻辑（readability → schema → 二次爬取 → LLM）
        """
        url = source_config["url"]

        # 检查是否已爬取过该 URL
        if self._tracker.is_crawled("web", url):
            logger.info(f"URL 已爬取，跳过: {url}")
            return []

        try:
            html = await self._fetch_html(url)
        except Exception as e:
            logger.error(f"获取网页失败 {url}: {e}")
            return []

        # 检测页面类型
        if self._is_list_page(html):
            logger.info(f"检测到列表页: {url}")
            return await self._crawl_list_page(html, url, user_selectors)
        else:
            return await self._crawl_detail_page(html, url, user_selectors)

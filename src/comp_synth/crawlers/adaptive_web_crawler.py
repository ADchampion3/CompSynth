from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from readability import Document

from comp_synth.config import settings
from comp_synth.crawlers.base import BaseCrawler
from comp_synth.crawlers.extractors import DOMExtractor
from comp_synth.schema.content_item import WebPageItem
from comp_synth.schema.site_chema import SiteSchema
from comp_synth.store.crawl_tracker import CrawlTracker
from comp_synth.store.schema_store import SchemaStore


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

    def _normalize_and_dedupe(
        self, items: list[dict], base_url: str
    ) -> list[dict]:
        """将 URL 转为绝对 URL 并去重"""
        seen: set[str] = set()
        result = []
        for item in items:
            url = item.get("url", "")
            if url:
                item["url"] = urljoin(base_url, url)
            if item.get("url") not in seen:
                seen.add(item.get("url"))
                result.append(item)
        return result

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
        logger.info(f"[_extract_list_items] 开始提取列表项 | site={site_name}")

        logger.info("[Step 1] user_selector | 尝试用户配置的 list_selectors")
        if user_selectors:
            logger.info(f"[Data] user_list_selectors: {user_selectors}")
            items = self._dom_extractor.extract_list_items_with_selectors(html, user_selectors)
            logger.info(f"[Result] {'成功' if items and self._has_valid_data(items) else '失败'} | 提取到 {len(items) if items else 0} 个条目")
            if items and self._has_valid_data(items):
                return self._normalize_and_dedupe(items, base_url)

        logger.info("[Step 2] db_selector | 尝试 DB 中已存储的 list_selectors")
        schema = self._schema_store.get(site_name)
        if schema and schema.selectors:
            logger.info(f"[Data] db_list_selectors: {schema.selectors}")
            items = self._dom_extractor.extract_list_items_with_selectors(html, schema.selectors)
            logger.info(f"[Result] {'成功' if items and self._has_valid_data(items) else '失败'} | 提取到 {len(items) if items else 0} 个条目")
            if items and self._has_valid_data(items):
                return self._normalize_and_dedupe(items, base_url)

        logger.info("[Step 3] llm_learning | 尝试 LLM 学习并提取")
        if self._schema_store.can_use_llm(site_name):
            logger.info(f"[Data] site={site_name}, can_use_llm=True")
            llm_items = await self._learn_list_item_schema(html, site_name)
            logger.info(f"[Result] {'成功' if llm_items else '失败'} | 提取到 {len(llm_items) if llm_items else 0} 个条目")
            if llm_items:
                return self._normalize_and_dedupe(llm_items, base_url)

        logger.info("[Step 4] heuristic | 尝试启发式方法提取")
        heuristic_items = await self._extract_list_items_heuristic(html, base_url)
        logger.info(f"[Result] 提取到 {len(heuristic_items)} 个条目")
        return heuristic_items

    async def _learn_list_item_schema(self, html: str, site_name: str) -> list[dict]:
        """使用 LLM 学习列表页结构并提取文章条目

        流程：
        1. LLM 生成 CSS selectors（只做结构分析）
        2. 用 CSS selectors 提取所有匹配元素（确定性提取，不会遗漏）
        """
        logger.info(f"[_learn_list_item_schema] 开始 LLM 学习 | site={site_name}")
        try:
            logger.info("[_learn_list_item_schema] 步骤1: LLM 生成 CSS selectors")
            list_selectors = await self._dom_extractor.generate_list_item_selectors(html)
            logger.info(f"[_learn_list_item_schema] selectors 生成完成: {list_selectors}")

            if not list_selectors:
                logger.warning("[_learn_list_item_schema] LLM 未生成有效 selectors")
                self._schema_store.mark_llm_called(site_name)
                return []

            logger.info("[_learn_list_item_schema] 步骤2: 使用 CSS selectors 提取所有条目")
            items = self._dom_extractor.extract_list_items_with_selectors(html, list_selectors)
            logger.info(f"[_learn_list_item_schema] CSS 提取完成 | 提取到 {len(items)} 个条目")


            selector = SiteSchema(site_name=site_name, site_url=items[0]["url"], selectors=list_selectors, last_llm_call=datetime.now())
            self._schema_store.save(selector)
            logger.info(f"[_learn_list_item_schema] list_selectors 已保存: {list_selectors}")

            # 标记 LLM 已调用
            self._schema_store.mark_llm_called(site_name)

            return items
        except Exception as e:
            logger.error(f"LLM 学习列表页结构失败: {e}")
            logger.exception(e)
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

        return items


    async def _fetch_article_detail(self, url: str) -> WebPageItem | None:
        """
        获取文章详情页内容（使用现有提取逻辑）
        """
        # 去重检查
        if self._tracker.is_crawled("web", url):
            logger.info(f"Web: {url} 已爬取, 跳过")
            return None
        try:
            html = await self._fetch_html(url)
            result = await self._extract_with_readability(html)
            summary_valid = result["summary"] and len(result["summary"]) > 100
            if result.get("content"):
                item = self._build_item(
                    url=url,
                    title=result.get("title", ""),
                    summary=result.get("summary") if summary_valid else result.get("content"),
                    site_name=self._detect_site(url),
                )
                return item
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
        raw_html_size = len(html)
        site_name = self._detect_site(url)

        logger.info(f"=== 列表页爬取开始 | URL: {url} | HTML大小: {raw_html_size} bytes ===")

        items = await self._extract_list_items(html, url, site_name, user_selectors)
        logger.info(f"[Raw] 提取到 {len(items)} 个列表条目")

        results = []

        for i, item_dict in enumerate(items):
            logger.info(f"[列表条目 {i+1}/{len(items)}] title={item_dict.get('title', '')[:30]}... | url={item_dict['url']}")

            if self._tracker.is_crawled("web", item_dict["url"]):
                logger.info(f"该列表已爬取，跳过: {item_dict['url']}")
                continue

            item_summary = item_dict.get("summary", "")
            summary_len = len(item_summary)

            # 只有 summary 缺失或太短时才爬详情页
            if not self._is_summary_enough(item_summary):
                logger.info(f"[列表条目 {i+1}] Summary 不足 ({summary_len} chars <= 100)，爬取详情页")
                # 去重检查：详情页爬取前检查是否已爬过
                if self._tracker.is_crawled("web", item_dict["url"]):
                    logger.debug(f"详情页已爬取，跳过: {item_dict['url']}")
                    continue
                detail_item = await self._fetch_article_detail(item_dict["url"])
                if detail_item:
                    logger.info(f"[列表条目 {i+1}] [Structured] {{title: {detail_item.title[:30]}..., summary长度: {len(detail_item.summary)}}}")
                    results.append(detail_item)
            else:
                # 直接使用列表页提取的元数据，不爬详情页
                item = self._build_item(
                    url=item_dict["url"],
                    title=item_dict.get("title", ""),
                    summary=item_summary,
                    site_name=site_name,
                )
                logger.info(f"[列表条目 {i+1}] [Structured] {{title: {item.title[:30]}..., summary长度: {len(item.summary)} (充足，跳过详情页)}}")
                results.append(item)

        logger.info(f"=== 列表页爬取结束 | 共 {len(results)} 条内容 ===")
        return results

    async def _crawl_detail_page(self, html: str, url: str, user_selectors: dict = None) -> list[WebPageItem]:
        """
        爬取详情页，优先使用 readability，content 不足时尝试 selectors 提取
        """
        raw_html_size = len(html)
        site_name = self._detect_site(url)

        logger.info(f"=== 详情页爬取开始 | URL: {url} | HTML大小: {raw_html_size} bytes ===")

        readability_result = await self._extract_with_readability(html)
        content = readability_result.get("content", "")
        title = readability_result.get("title", "")
        summary = readability_result.get("summary", "")

        # 如果 readability 提取的内容太短，尝试 selectors
        if len(content) < 100:
            selectors = user_selectors
            if not selectors:
                schema = self._schema_store.get(site_name)
                if schema and schema.selectors:
                    selectors = schema.selectors

            if selectors:
                logger.info("[Detail] readability 内容不足，尝试 selectors 提取")
                soup = BeautifulSoup(html, "html.parser")
                sel_title = soup.select_one(selectors.get("title", "h1"))
                sel_content = soup.select_one(selectors.get("content", "article"))
                if sel_title:
                    title = sel_title.get_text(strip=True)
                if sel_content:
                    content = sel_content.get_text(separator="\n", strip=True)
                    if not summary and len(content) > 100:
                        summary = content[:200]

        logger.info(f"[Result] title={title[:30] if title else 'N/A'}... | content长度={len(content)}")

        item = self._build_item(
            url=url,
            title=title,
            summary=content or summary,
            site_name=site_name,
        )
        logger.info(f"[Structured] {{title: {item.title[:30]}..., summary长度: {len(item.summary)}}}")
        return [item]


    def _build_item(
        self,
        url: str,
        title: str = "",
        summary: str = "",
        site_name: str = "",
    ) -> WebPageItem:
        """构建 WebPageItem，最低保障 url + title"""
        return WebPageItem(
            url=url,
            title=title or url,  # title 最低保障为 url
            summary=summary,
            metadata={"site_name": site_name},
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

        try:
            html = await self._fetch_html(url)
        except Exception as e:
            logger.error(f"获取网页失败 {url}: {e}")
            return []

        result = []
        # 检测页面类型
        if self._is_list_page(html):
            logger.info(f"检测到列表页: {url}")
            result = await self._crawl_list_page(html, url, user_selectors)
        else:
            # 直接爬取详情页前检查是否已爬过
            if self._tracker.is_crawled("web", url):
                logger.info(f"详情页已爬取，跳过: {url}")
                return result
            result = await self._crawl_detail_page(html, url, user_selectors)
        if result:
            self._tracker.save_articles([
                {
                    "article_id": item.id,
                    "title": item.title,
                    "summary": item.summary,
                    "published_at": item.published_at.isoformat() if item.published_at else None,
                }
                for item in result
            ])
        return result

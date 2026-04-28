from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from loguru import logger
from readability import Document

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
        self._tracker = CrawlTracker()
        self._schema_store = SchemaStore()
        self._dom_extractor = DOMExtractor()

    def _detect_site(self, url: str) -> str:
        """根据 URL 检测站点名称（使用域名）"""
        parsed = urlparse(url)
        return parsed.netloc or "unknown"

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

    def _filter_items_by_container(self, items: list[dict]) -> list[dict]:
        """
        对列表页条目进行阈值过滤。

        策略（先时间后数量）：
        1. 有 published_at 的 item → 时间阈值过滤（超过阈值的丢弃）
        2. 无 published_at 的 item → 数量阈值截断（超量的丢弃）
        3. 合并两组结果返回
        """
        from comp_synth.config import settings

        time_threshold_days = settings.list_page_time_threshold_days
        count_threshold = settings.list_page_count_threshold

        items_with_time = []
        items_without_time = []

        for item in items:
            published_at = item.get("published_at")
            if published_at is not None:
                items_with_time.append(item)
            else:
                items_without_time.append(item)

        # ① 有时间的：时间阈值过滤
        if time_threshold_days > 0:
            cutoff = datetime.now() - timedelta(days=time_threshold_days)
            items_with_time = [
                item for item in items_with_time
                if item.get("published_at") and item["published_at"] >= cutoff
            ]

        # ② 无时间的：数量阈值截断
        if count_threshold > 0:
            items_without_time = items_without_time[:count_threshold]

        return items_with_time + items_without_time

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
        user_selectors: list[dict[str, str]] | None = None,
    ) -> list[dict]:
        """
        从列表页提取所有文章条目，返回 [{"url": "", "title": "", "summary": ""}, ...]

        提取策略（优先级从高到低）：
        1. 用户配置的 selectors（支持多组选择器）
        2. DB 中已存储的 list_selectors（支持多组选择器）
        3. LLM 学习并提取
        4. 启发式后备方案
        """
        logger.info("[_extract_list_items] 开始提取列表项 | site={site_name}", site_name=site_name)

        logger.info("[step_1] user_selector | 尝试用户配置的 selectors")
        if user_selectors:
            logger.info("[step_1] user_selectors={selectors}", selectors=user_selectors)
            items = self._dom_extractor.extract_list_items_with_selectors(html, user_selectors)
            success = items and self._has_valid_data(items)
            logger.info("[step_1] result={result} | extracted_count={count}", result="成功" if success else "失败", count=len(items) if items else 0)
            if success:
                return self._normalize_and_dedupe(items, base_url)

        logger.info("[step_2] db_selector | 尝试 DB 中已存储的 selectors")
        schema = self._schema_store.get(site_name)
        if schema and schema.selectors:
            logger.info("[step_2] db_selectors={selectors}", selectors=schema.selectors)
            items = self._dom_extractor.extract_list_items_with_selectors(html, schema.selectors)
            success = items and self._has_valid_data(items)
            logger.info("[step_2] result={result} | extracted_count={count}", result="成功" if success else "失败", count=len(items) if items else 0)
            if success:
                return self._normalize_and_dedupe(items, base_url)

        logger.info("[step_3] llm_learning | 尝试 LLM 学习并提取")
        if self._schema_store.can_use_llm(site_name):
            logger.info("[step_3] site={site_name} | can_use_llm=True", site_name=site_name)
            llm_items = await self._learn_list_item_schema(html, site_name, base_url)
            success = bool(llm_items)
            logger.info("[step_3] result={result} | extracted_count={count}", result="成功" if success else "失败", count=len(llm_items) if llm_items else 0)
            if llm_items:
                return self._normalize_and_dedupe(llm_items, base_url)

        logger.info("[step_4] heuristic | 尝试启发式方法提取")
        heuristic_items = await self._extract_list_items_heuristic(html, base_url)
        logger.info("[step_4] extracted_count={count}", count=len(heuristic_items))
        return heuristic_items

    async def _learn_list_item_schema(self, html: str, site_name: str, base_url: str) -> list[dict]:
        """使用 LLM 学习列表页结构并提取文章条目

        流程：
        1. LLM 生成 CSS selectors（只做结构分析）
        2. 用 CSS selectors 提取所有匹配元素（确定性提取，不会遗漏）
        """
        logger.info("[_learn_list_item_schema] 开始 LLM 学习 | site={site_name}", site_name=site_name)
        try:
            logger.info("[_learn_list_item_schema] 步骤1: LLM 生成 CSS selectors")
            list_selectors = await self._dom_extractor.generate_list_item_selectors(html)
            logger.info("[_learn_list_item_schema] selectors 生成完成 | selectors={selectors}", selectors=list_selectors)

            if not list_selectors:
                logger.warning("[_learn_list_item_schema] LLM 未生成有效 selectors")
                self._schema_store.mark_llm_called(site_name)
                return []

            logger.info("[_learn_list_item_schema] 步骤2: 使用 CSS selectors 提取所有条目")
            items = self._dom_extractor.extract_list_items_with_selectors(html, list_selectors)
            logger.info("[_learn_list_item_schema] CSS 提取完成 | extracted_count={count}", count=len(items))

            selector = SiteSchema(site_name=site_name, site_url=base_url, selectors=list_selectors, last_llm_call=datetime.now())
            self._schema_store.save(selector)
            logger.info("[_learn_list_item_schema] selectors 已保存 | selectors={selectors}", selectors=list_selectors)

            self._schema_store.mark_llm_called(site_name)

            return items
        except Exception as e:
            logger.error("[_learn_list_item_schema] LLM 学习列表页结构失败 | error={error}", error=e)
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
                    content=result.get("content", ""),
                    site_name=self._detect_site(url),
                )
                return item
        except Exception as e:
            logger.warning(f"详情页爬取失败 {url}: {e}")
        return None

    async def fetch_detail(self, item: WebPageItem, site_name: str) -> WebPageItem | None:
        """爬取详情页（始终执行）"""
        return await self._fetch_article_detail(item.url)

    async def _crawl_list_page(self, html: str, url: str, user_selectors: list[dict[str, str]] | None = None) -> list[WebPageItem]:
        """
        爬取列表页，提取所有文章条目
        核心原则：只有 summary 缺失或太短时才爬详情页
        """
        raw_html_size = len(html)
        site_name = self._detect_site(url)

        logger.info("[crawl_list_page] 开始爬取 | url={url} | html_size={size}", url=url, size=raw_html_size)

        items = await self._extract_list_items(html, url, site_name, user_selectors)
        logger.info("[crawl_list_page] 提取到 {count} 个列表条目", count=len(items))

        # 阈值过滤
        if items:
            items = self._filter_items_by_container(items)
            logger.info("[crawl_list_page] 阈值过滤后剩余 {count} 个条目", count=len(items))

        results = []

        for i, item_dict in enumerate(items):
            title_preview = item_dict.get('title', '')[:30]
            logger.info("[crawl_list_page] item {index}/{total} | title={title}... | url={url}", index=i+1, total=len(items), title=title_preview, url=item_dict['url'])

            item_summary = item_dict.get("summary", "")

            # 构建列表页条目（不含去重和详情抓取，由 ContentManager 处理）
            list_item = self._build_item(
                url=item_dict["url"],
                title=item_dict.get("title", ""),
                summary=item_summary,
                site_name=site_name,
            )
            results.append(list_item)

        logger.info("[crawl_list_page] 爬取结束 | total_items={count}", count=len(results))
        return results

    async def _crawl_detail_page(self, html: str, url: str) -> list[WebPageItem]:
        """
        爬取详情页，优先使用 readability
        """
        raw_html_size = len(html)
        site_name = self._detect_site(url)

        logger.info("[crawl_detail_page] 开始爬取 | url={url} | html_size={size}", url=url, size=raw_html_size)

        readability_result = await self._extract_with_readability(html)
        content = readability_result.get("content", "")
        title = readability_result.get("title", "")
        summary = readability_result.get("summary", "")

        title_preview = title[:30] if title else "N/A"
        logger.info("[crawl_detail_page] result | title={title}... | content_length={length}", title=title_preview, length=len(content))

        item = self._build_item(
            url=url,
            title=title,
            summary=content or summary,
            content=content,
            site_name=site_name,
        )
        logger.info("[crawl_detail_page] item | title={title}... | summary_length={length}", title=item.title[:30], length=len(item.summary))
        return [item]


    def _build_item(
        self,
        url: str,
        title: str = "",
        summary: str = "",
        content: str = "",
        site_name: str = "",
    ) -> WebPageItem:
        """构建 WebPageItem，最低保障 url + title"""
        return WebPageItem(
            url=url,
            title=title or url,  # title 最低保障为 url
            summary=summary,
            content=content,
            metadata={"site_name": site_name},
        )

    async def fetch_page(self, url: str, user_selectors: list[dict[str, str]] | None = None) -> list[WebPageItem]:
        """
        从单个页面抓取内容（不含去重和持久化，由 ContentManager 处理）。

        流程：
        1. 获取 HTML
        2. 检测页面类型：列表页 vs 详情页
        3. 列表页：提取所有文章条目
        4. 详情页：使用 readability 提取
        """
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
            return await self._crawl_detail_page(html, url)

    async def fetch(self, source_config: dict, user_selectors: list[dict[str, str]] | None = None) -> list[WebPageItem]:
        """兼容接口，内部委托给 fetch_page"""
        return await self.fetch_page(source_config["url"], user_selectors)

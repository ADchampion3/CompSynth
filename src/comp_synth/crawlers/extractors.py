import asyncio
import re
from datetime import datetime
from typing import List
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel

from comp_synth.llm_provider import registry as _llm_registry
from comp_synth.prompt import DOM_PROMPTS
from comp_synth.utils.date_parser import parse_published_at


class ListItemSelector(BaseModel):
    """文章框架 CSS Selector"""
    item_container: str = ""
    url: str = ""
    title: str = ""
    summary: str = ""
    time: str = ""  # 时间元素 CSS selector


class ListItemSelectors(BaseModel):
    data: list[ListItemSelector]


class ContainerFragment(BaseModel):
    """单个文章容器片段"""
    description: str = ""
    container_selector: str = ""
    fragment_html: str = ""


class ContainerFragments(BaseModel):
    data: list[ContainerFragment]


class DOMExtractor:
    """使用 LLM 从 HTML DOM 中提取结构化内容"""

    @property
    def llm(self):
        return _llm_registry.llm_registry.get()

    def _preprocess_html(self, html: str) -> str:
        """Stage 0: 清洗 HTML，移除噪声元素和冗余属性"""
        soup = BeautifulSoup(html, "html.parser")
        soup = self._preprocess_html_soup(soup)
        return str(soup)

    def _preprocess_html_soup(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Soup version of _preprocess_html. Operates on soup objects directly."""
        # 1. Remove noise tags
        noise_tags = [
            "script", "style", "nav", "footer", "header",
            "noscript", "iframe", "svg", "img", "input", "button",
            "link", "meta", "head", "audio", "video", "canvas"
        ]
        for tag in soup.find_all(noise_tags):
            tag.decompose()

        # 2. Remove on* and data-* attributes
        for elem in soup.find_all():
            attrs_to_remove = [a for a in elem.attrs if a.startswith("on") or a.startswith("data-")]
            for attr in attrs_to_remove:
                del elem[attr]

        # 3. Strip noise classes
        for elem in soup.find_all(class_=True):
            classes = elem.get("class", [])
            cleaned = [c for c in classes if not any(
                self._matches_at_boundary(c.lower(), n) for n in self._PREPROCESS_NOISE_CLASSES
            )]
            if cleaned:
                elem["class"] = cleaned
            else:
                del elem["class"]

        return soup

    _PREPROCESS_NOISE_CLASSES = [
        "col-", "row", "container", "navbar", "theme-", "no-js",
        "page-", "widget", "sidebar", "menu", "footer", "header",
        "breadcrumb", "unittest", "gutter", "align", "visible",
        "hidden", "active", "hover", "focus", "disabled",
    ]

    _NOISE_CLASS_PATTERNS = [
        "flex", "grid", "layout-", "md:", "lg:", "sm:", "col-", "row-",
        "offset-", "padding-", "margin-", "gap-", "items-", "justify-",
        "w-", "h-", "min-", "max-", "text-center", "text-left", "text-right",
        "ad-", "ad_", "adsense", "google-ad", "sponsor", "promotion", "banner",
        "share-", "share_", "social-", "social_", "addtoany", "sharethis",
        "cookie-", "cookie_", "consent-", "consent_", "gdpr-",
        "sidebar", "widget", "widget-area",
        "breadcrumb", "breadcrumbs",
        "pager", "pagination", "page-nav",
        "search-", "search_", "newsletter-", "newsletter_",
        "related-", "recommend-", "similar-",
    ]

    _DEEP_CLEAN_PATTERNS = {
        "ads": ["ad-", "ad_", "advertisement", "sponsor", "promotion", "banner", "google-ad", "adsense"],
        "social": ["share-", "share_", "social-", "social_", "weibo", "twitter", "facebook-share", "addtoany", "sharethis"],
        "cookie": ["cookie-", "cookie_", "consent-", "consent_", "gdpr-", "privacy-banner", "cookie-notice"],
        "comments": ["comment-list", "comment-respond", "comments"],
        "related": ["related-", "related_", "recommend-", "recommend_", "similar-", "also-read", "you-may-also", "read-more"],
        "pagination": ["pager", "pagination", "page-nav"],
        "breadcrumbs": ["breadcrumb", "breadcrumbs"],
        "sidebar": ["sidebar", "widget", "widget-area"],
        "search": ["search-", "search_", "newsletter-", "newsletter_"],
    }

    _DEEP_CLEAN_IDS = {
        "comments", "respond", "comment-respond",
    }

    _URL_PARAMS_TO_STRIP = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                            "fbclid", "ref", "source", "spm", "from"}

    @staticmethod
    def _matches_at_boundary(class_name: str, pattern: str) -> bool:
        """Check if pattern matches at a word boundary in the class name.

        Matches at start of string or after a delimiter (- or _).
        Prevents 'ad-' from matching 'articlelist-module-...'.
        """
        idx = class_name.find(pattern)
        while idx != -1:
            if idx == 0:
                return True
            prev = class_name[idx - 1]
            if prev in "-_":
                return True
            idx = class_name.find(pattern, idx + 1)
        return False

    def _is_noise_class(self, class_name: str) -> bool:
        """Check if a class name matches noise patterns at word boundaries."""
        lower = class_name.lower()
        return any(self._matches_at_boundary(lower, p) for p in self._NOISE_CLASS_PATTERNS)

    def _matches_noise_pattern(self, elem_classes: list[str], elem_id: str) -> bool:
        """Check if element matches any deep-clean noise pattern."""
        for category, patterns in self._DEEP_CLEAN_PATTERNS.items():
            if any(self._matches_at_boundary(cls, p) for cls in elem_classes for p in patterns):
                return True
            if category == "comments" and elem_id in self._DEEP_CLEAN_IDS:
                return True
        return False

    def _is_hidden(self, elem: Tag) -> bool:
        """Check if element is hidden via style, hidden attr, or aria-hidden."""
        if elem.get("hidden") is not None or elem.get("aria-hidden") == "true":
            return True
        style = (elem.get("style") or "").lower().replace(" ", "")
        return "display:none" in style or "visibility:hidden" in style

    def _deep_clean(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Layer 1: Remove content noise elements (ads, social, cookie, comments, etc.)"""
        for elem in soup.find_all(True):
            if elem.attrs is None:
                continue
            elem_classes = [c.lower() for c in elem.get("class", [])]
            elem_id = (elem.get("id") or "").lower()

            if self._matches_noise_pattern(elem_classes, elem_id):
                elem.decompose()
                continue

            if self._is_hidden(elem):
                elem.decompose()
                continue

            if elem.name == "aside":
                elem.decompose()
                continue

            if elem.name == "form" and not elem.find_parent("article"):
                elem.decompose()

        return soup

    def _strip_attributes(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Layer 2: Strip non-semantic attributes, normalize URLs."""
        attrs_to_remove = {"style", "width", "height", "align", "valign", "border",
                           "cellpadding", "cellspacing", "tabindex", "draggable",
                           "contenteditable", "target", "rel"}

        for elem in soup.find_all(True):
            # Remove presentation attributes
            for attr in list(elem.attrs.keys()):
                if attr in attrs_to_remove:
                    del elem[attr]

            # Normalize href URLs
            if elem.name == "a" and elem.get("href"):
                elem["href"] = self._clean_url(elem["href"])

        return soup

    def _clean_url(self, url: str) -> str:
        """Strip tracking parameters from URLs."""
        if not url or not url.startswith(("http://", "https://", "/")):
            return url
        try:
            parsed = urlparse(url)
            if not parsed.query:
                return url
            params = parse_qs(parsed.query, keep_blank_values=True)
            cleaned = {k: v for k, v in params.items() if k not in self._URL_PARAMS_TO_STRIP}
            new_query = urlencode(cleaned, doseq=True) if cleaned else ""
            return urlunparse(parsed._replace(query=new_query))
        except Exception:
            return url

    async def identify_container_fragments(self, html: str, *, cleaned_html: str | None = None) -> list[ContainerFragment]:
        """Stage 1: 从列表页 HTML 中识别文章容器片段（去重）

        Args:
            html: Raw HTML (used when cleaned_html is not provided)
            cleaned_html: Pre-cleaned HTML to use directly (skips preprocessing)
        """
        if cleaned_html is None:
            cleaned_html = self._preprocess_html(html)
        html_preview = cleaned_html[:20000] if len(cleaned_html) > 20000 else cleaned_html

        try:
            structured_llm = self.llm.with_structured_output(ContainerFragments)
            logger.info("[identify_container_fragments] Stage 1: 识别文章容器片段")
            result: ContainerFragments = await structured_llm.ainvoke([
                SystemMessage(content=DOM_PROMPTS["CONTAINER_DISCOVERY"]),
                HumanMessage(content=f"请分析以下列表页 HTML，识别文章容器并返回每个容器类型的 HTML 片段：\n\n{html_preview}"),
            ])
            return result.data if result else []
        except Exception as e:
            logger.warning("[identify_container_fragments] Stage 1 容器识别失败 | error={error}", error=e)
            return []

    async def generate_selectors_from_fragment(self, fragment: ContainerFragment) -> list[dict[str, str]]:
        """Stage 2: 从容器 HTML 片段生成 item_selectors"""
        try:
            structured_llm = self.llm.with_structured_output(ListItemSelectors)
            logger.info("[generate_selectors_from_fragment] Stage 2: 从容器片段生成 selectors | container={container}", container=fragment.container_selector)
            result: ListItemSelectors = await structured_llm.ainvoke([
                SystemMessage(content=DOM_PROMPTS["LIST_ITEM_SELECTOR_FROM_FRAGMENT"]),
                HumanMessage(content=f"请分析以下文章容器 HTML 片段，生成 CSS selectors：\n\n{fragment.fragment_html}"),
            ])
            if not result or not result.data:
                return []
            selectors = [item.model_dump() for item in result.data]
            for s in selectors:
                if not s.get("item_container"):
                    s["item_container"] = fragment.container_selector
            return selectors
        except Exception as e:
            logger.warning("[generate_selectors_from_fragment] Stage 2 selectors 生成失败 | error={error}", error=e)
            return []

    async def generate_list_item_selectors(self, html: str) -> List[dict[str, str]]:
        """Main entry point: preprocess HTML and generate CSS selectors.

        Args:
            html: Raw HTML content

        Returns:
            List[dict[str, str]]: CSS selector groups
        """
        # Parse once, run 3-layer cleaning pipeline
        soup = BeautifulSoup(html, "html.parser")
        soup = self._preprocess_html_soup(soup)
        soup = self._deep_clean(soup)
        soup = self._strip_attributes(soup)
        cleaned_html = str(soup)

        return await self._generate_selectors_legacy_two_stage(cleaned_html)

    async def _generate_selectors_legacy_two_stage(self, cleaned_html: str) -> List[dict[str, str]]:
        """Legacy two-stage flow using cleaned HTML."""
        # Stage 1: identify container fragments
        fragments = await self.identify_container_fragments(cleaned_html, cleaned_html=cleaned_html)
        if not fragments:
            return await self._generate_selectors_legacy(cleaned_html)

        # Stage 2: generate selectors from fragments
        results = await asyncio.gather(*[
            self.generate_selectors_from_fragment(f) for f in fragments
        ], return_exceptions=True)

        all_selectors: list[dict[str, str]] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("[_generate_selectors_legacy_two_stage] Stage 2 失败 | error={error}", error=result)
            else:
                all_selectors.extend(result)

        return all_selectors if all_selectors else await self._generate_selectors_legacy(cleaned_html)

    async def _generate_selectors_legacy(self, html: str) -> List[dict[str, str]]:
        """原始单阶段 LLM selector 生成（后备方案）"""
        html_preview = html[:15000]

        try:
            structured_llm = self.llm.with_structured_output(ListItemSelectors)
            logger.info("[_generate_selectors_legacy] 使用原始方案生成 CSS selectors")
            result: ListItemSelectors = await structured_llm.ainvoke([
                SystemMessage(content=DOM_PROMPTS["LIST_ITEM_SELECTOR"]),
                HumanMessage(content=f"请分析以下列表页 HTML 结构并生成 selectors：\n\n{html_preview}"),
            ])
            if not result or not result.data:
                return []
            return [item.model_dump() for item in result.data]
        except Exception as e:
            logger.warning("[_generate_selectors_legacy] 原始方案 with_structured_output 失败 | error={error}", error=e)
            return []

    def extract_list_items_with_selectors(self, html: str, list_selectors: list[dict[str, str]]) -> list[dict]:
        """使用 CSS selectors 从列表页 HTML 中提取所有文章条目信息

        Args:
            html: HTML 内容
            list_selectors: CSS 选择器列表，每个 dict 包含一组选择器
                           支持多组选择器用于提取同一页面的多个容器内容

        Returns:
            提取到的文章条目列表
        """
        logger.info("[extract_list_items_with_selectors] html_size={size} | selectors_count={count}", size=len(html), count=len(list_selectors))
        soup = BeautifulSoup(html, "html.parser")
        all_items = []
        seen_urls: set[str] = set()

        for selector_idx, selectors in enumerate(list_selectors):
            logger.info("[extract_list_items_with_selectors] 使用第 {index} 组选择器 | selectors={selectors}", index=selector_idx + 1, selectors=selectors)

            item_container = selectors.get("item_container", "article")
            url_selector = selectors.get("url", "a[href]")
            title_selector = selectors.get("title", "h2")
            summary_selector = selectors.get("summary", "p")
            time_selector = selectors.get("time", "")

            containers = soup.select(item_container)
            logger.info("[extract_list_items_with_selectors] 第 {index} 组选择器找到 {count} 个容器", index=selector_idx + 1, count=len(containers))

            for container in containers:
                # 提取 URL：优先从 href 属性获取，其次从文本中用正则提取
                url = ""
                link_elem = container.select_one(url_selector)
                if link_elem:
                    # 方案1：直接获取 href 属性
                    if link_elem.name == "a" and link_elem.get("href"):
                        url = link_elem["href"]
                    elif link_elem.get("href"):
                        url = link_elem["href"]
                    else:
                        # 方案2：查找容器内的 <a> 标签
                        anchor = link_elem.find("a", href=True)
                        if anchor:
                            url = anchor["href"]
                        else:
                            # 方案3：从文本中用正则提取 URL
                            text = link_elem.get_text()
                            url_match = re.search(r"https?://[^\s<>\"']+", text)
                            if url_match:
                                url = url_match.group()

                # 容器本身就是 <a> 时，select_one 只搜索后代，取容器自身的 href
                if not url and container.name == "a" and container.get("href"):
                    url = container["href"]

                title = ""
                if title_selector:
                    try:
                        title_elem = container.select_one(title_selector)
                    except Exception:
                        title_elem = None
                    if title_elem:
                        title = title_elem.get_text(strip=True)

                summary = ""
                if summary_selector:
                    try:
                        summary_elem = container.select_one(summary_selector)
                    except Exception:
                        summary_elem = None
                    if summary_elem:
                        summary = summary_elem.get_text(strip=True)

                published_at = None
                if time_selector:
                    try:
                        time_elem = container.select_one(time_selector)
                    except Exception:
                        time_elem = None
                    if time_elem:
                        # 优先取 datetime 属性
                        dt = time_elem.get("datetime", "")
                        if dt:
                            try:
                                published_at = datetime.fromisoformat(dt.replace("Z", "+00:00"))
                            except Exception:
                                pass
                        # 其次取文本内容
                        if published_at is None:
                            time_text = time_elem.get_text(strip=True)
                            if time_text:
                                published_at = parse_published_at(time_text)

                if title and url:
                    if url not in seen_urls:
                        seen_urls.add(url)
                        all_items.append({
                            "url": url,
                            "title": title,
                            "summary": summary,
                            "published_at": published_at,
                        })

        logger.info("[extract_list_items_with_selectors] 提取完成 | extracted_count={count}（去重后）", count=len(all_items))
        return all_items

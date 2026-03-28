import asyncio
import re
from typing import List

from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel

from comp_synth.llm_provider.registry import llm_registry
from comp_synth.prompt import DOM_PROMPTS


class ListItemSelector(BaseModel):
    """文章框架 CSS Selector"""
    item_container: str = ""
    url: str = ""
    title: str = ""
    summary: str = ""


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

    def __init__(self):
        self._llm = llm_registry.get()

    def _preprocess_html(self, html: str) -> str:
        """Stage 0: 清洗 HTML，移除噪声元素和冗余属性"""
        soup = BeautifulSoup(html, "html.parser")

        # 1. 移除噪声元素
        noise_tags = [
            "script", "style", "nav", "footer", "header",
            "noscript", "iframe", "svg", "img", "input", "button",
            "link", "meta", "head", "audio", "video", "canvas"
        ]
        for tag in soup.find_all(noise_tags):
            tag.decompose()

        # 2. 移除内联事件处理器和 data-* 属性
        for elem in soup.find_all():
            attrs_to_remove = [a for a in elem.attrs if a.startswith("on") or a.startswith("data-")]
            for attr in attrs_to_remove:
                del elem[attr]

        # 3. 精简 class 属性（移除噪声 class）
        noise_class_patterns = [
            "col-", "row", "container", "navbar", "theme-", "no-js",
            "page-", "widget", "sidebar", "menu", "footer", "header",
            "breadcrumb", "unittest", "gutter", "align", "visible",
            "hidden", "active", "hover", "focus", "disabled"
        ]
        for elem in soup.find_all(class_=True):
            classes = elem.get("class", [])
            cleaned = [c for c in classes if not any(n in c.lower() for n in noise_class_patterns)]
            if cleaned:
                elem["class"] = " ".join(cleaned)
            else:
                del elem["class"]

        return str(soup)

    async def identify_container_fragments(self, html: str) -> list[ContainerFragment]:
        """Stage 1: 从列表页 HTML 中识别文章容器片段（去重）"""
        cleaned_html = self._preprocess_html(html)
        html_preview = cleaned_html[:20000] if len(cleaned_html) > 20000 else cleaned_html

        try:
            structured_llm = self._llm.with_structured_output(ContainerFragments)
            logger.info("[identify_container_fragments] Stage 1: 识别文章容器片段")
            result: ContainerFragments = await structured_llm.ainvoke([
                SystemMessage(content=DOM_PROMPTS["CONTAINER_DISCOVERY"]),
                HumanMessage(content=f"请分析以下列表页 HTML，识别文章容器并返回每个容器类型的 HTML 片段：\n\n{html_preview}"),
            ])
            return result.data
        except Exception as e:
            logger.warning("[identify_container_fragments] Stage 1 容器识别失败 | error={error}", error=e)
            return []

    async def generate_selectors_from_fragment(self, fragment: ContainerFragment) -> list[dict[str, str]]:
        """Stage 2: 从容器 HTML 片段生成 item_selectors"""
        try:
            structured_llm = self._llm.with_structured_output(ListItemSelectors)
            logger.info("[generate_selectors_from_fragment] Stage 2: 从容器片段生成 selectors | container={container}", container=fragment.container_selector)
            result: ListItemSelectors = await structured_llm.ainvoke([
                SystemMessage(content=DOM_PROMPTS["LIST_ITEM_SELECTOR_FROM_FRAGMENT"]),
                HumanMessage(content=f"请分析以下文章容器 HTML 片段，生成 CSS selectors：\n\n{fragment.fragment_html}"),
            ])
            selectors = [item.model_dump() for item in result.data]
            for s in selectors:
                if not s.get("item_container"):
                    s["item_container"] = fragment.container_selector
            return selectors
        except Exception as e:
            logger.warning("[generate_selectors_from_fragment] Stage 2 selectors 生成失败 | error={error}", error=e)
            return []

    async def generate_list_item_selectors(self, html: str) -> List[dict[str, str]]:
        """两阶段 LLM selector 提取

        Stage 0: HTML 预处理（清洗噪声）
        Stage 1: LLM 识别文章容器片段（去重）
        Stage 2: LLM 从每个片段生成 item_selectors

        Returns:
            List[dict[str, str]]: CSS 选择器列表
        """
        # Stage 1: 识别容器片段
        fragments = await self.identify_container_fragments(html)
        if not fragments:
            logger.warning("[generate_list_item_selectors] Stage 1 未识别到任何容器片段，尝试原始方案")
            return await self._generate_selectors_legacy(html)

        results = await asyncio.gather(*[
            self.generate_selectors_from_fragment(fragment)
            for fragment in fragments
        ], return_exceptions=True)
        all_selectors = []
        failed_count = 0
        for result in results:
            if isinstance(result, Exception):
                failed_count += 1
                logger.warning("[generate_list_item_selectors] Stage 2 片段处理失败 | error={error}", error=result)
            else:
                all_selectors.extend(result)
        if failed_count:
            logger.warning("[generate_list_item_selectors] Stage 2 | failed_count={failed}/{total}", failed=failed_count, total=len(fragments))

        if not all_selectors:
            logger.warning("[generate_list_item_selectors] Stage 2 未生成有效 selectors，尝试原始方案")
            return await self._generate_selectors_legacy(html)

        return all_selectors

    async def _generate_selectors_legacy(self, html: str) -> List[dict[str, str]]:
        """原始单阶段 LLM selector 生成（后备方案）"""
        html_preview = html[:15000]

        try:
            structured_llm = self._llm.with_structured_output(ListItemSelectors)
            logger.info("[_generate_selectors_legacy] 使用原始方案生成 CSS selectors")
            result: ListItemSelectors = await structured_llm.ainvoke([
                SystemMessage(content=DOM_PROMPTS["LIST_ITEM_SELECTOR"]),
                HumanMessage(content=f"请分析以下列表页 HTML 结构并生成 selectors：\n\n{html_preview}"),
            ])
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

            item_container = selectors.get("item_container", "") or "article"
            url_selector = selectors.get("url", "") or "a[href]"
            title_selector = selectors.get("title", "") or "h2, h3"
            summary_selector = selectors.get("summary", "") or "p"

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

                # 提取标题
                title = ""
                title_elem = container.select_one(title_selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)

                # 提取摘要
                summary = ""
                summary_elem = container.select_one(summary_selector)
                if summary_elem:
                    summary = summary_elem.get_text(strip=True)

                if title and url:  # 至少需要标题和 URL
                    # 去重：基于 URL 去重
                    if url not in seen_urls:
                        seen_urls.add(url)
                        all_items.append({
                            "url": url,
                            "title": title,
                            "summary": summary,
                        })

        logger.info("[extract_list_items_with_selectors] 提取完成 | extracted_count={count}（去重后）", count=len(all_items))
        return all_items

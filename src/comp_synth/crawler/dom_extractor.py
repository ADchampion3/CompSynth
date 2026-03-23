import json
import re
from typing import Any

from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel

from comp_synth.config import settings
from comp_synth.llm.registry import LLMRegistry
from comp_synth.schemas.web import WebPageItem


class ExtractedContent(BaseModel):
    """详情页内容提取"""
    title: str = ""
    author: str = ""
    published_at: str = ""
    content: str = ""
    tags: list[str] = []


class DetailPageSelectors(BaseModel):
    """详情页 CSS Selectors"""
    title: str = ""
    author: str = ""
    published_at: str = ""
    content: str = ""
    tags: str = ""


class ListItemSelectors(BaseModel):
    """列表页 CSS Selectors"""
    item_container: str = ""
    url: str = ""
    title: str = ""
    summary: str = ""


class ListItemsResult(BaseModel):
    """列表页文章条目提取结果"""
    items: list[dict] = []


class DOMExtractor:
    """使用 LLM 从 HTML DOM 中提取结构化内容"""

    SYSTEM_PROMPT = """你是一个专业的网页内容提取专家。你的任务是从给定 HTML 中提取结构化信息。

需要提取的字段：
- title: 文章标题（通常在 h1 或 .title 中）
- author: 作者名称（通常在 .author, .byline, [rel="author"] 中）
- published_at: 发布时间（尝试从 time[datetime] 或其他时间元素中提取）
- content: 文章正文内容（主要段落，不包含导航、侧边栏等）
- tags: 文章标签列表（通常在 .tags, .categories 中）

请直接返回 JSON 格式，不要 markdown 代码块：
{
    "title": "...",
    "author": "...",
    "published_at": "ISO 格式时间，如 2024-01-15T10:30:00",
    "content": "提取的正文内容...",
    "tags": ["tag1", "tag2"]
}

规则：
- 只提取主要文章内容，不要包含页头、导航、侧边栏、广告等
- content 应该是一段连续的文本
- 如果某个字段不存在，用空字符串 ""
- tags 始终是数组，即使只有一个标签
"""

    SELECTOR_PROMPT = """分析以下 HTML 结构，生成 CSS selectors 映射，用于提取相同站点的后续页面。

需要生成 selectors 的字段：
- title: 文章标题
- author: 作者
- published_at: 发布时间
- content: 文章正文
- tags: 标签

请直接返回 JSON 格式：
{
    "title": "CSS selector for title",
    "author": "CSS selector for author",
    "published_at": "CSS selector for published_at",
    "content": "CSS selector for content",
    "tags": "CSS selector for tags"
}

规则：
- 使用简洁高效的 CSS 选择器
- 优先使用 class 和 id
- 考虑文章的典型 HTML 结构（如 article, .post-content, .entry-content 等）
"""

    LIST_ITEM_SELECTOR_PROMPT = """分析以下列表页 HTML 结构，生成 CSS selectors 映射，用于提取列表中的每个文章条目。

需要生成 selectors 的字段：
- item_container: 包裹整个文章条目的容器选择器（如 article, .post-item, .entry）
- url: 文章链接的选择器（通常是容器内的 <a> 标签）
- title: 文章标题的选择器（通常是 h1-h6 或带标题类的元素）
- summary: 文章摘要的选择器（通常是 p.summary, .excerpt, .description 等）

请直接返回 JSON 格式：
{
    "item_container": "CSS selector for item container",
    "url": "CSS selector for article link",
    "title": "CSS selector for article title",
    "summary": "CSS selector for article summary"
}

规则：
- item_container 应该选中列表中的每一个文章条目
- url 应该是容器内的链接选择器
- title 和 summary 是容器内相应元素的选择器
- 使用简洁高效的 CSS 选择器
- 优先使用 class 和 id
"""

    LIST_ITEM_EXTRACT_PROMPT = """你是一个专业的网页内容提取专家。你的任务是从列表页 HTML 中提取所有文章条目信息。

需要提取的字段：
- url: 文章详情页的完整 URL
- title: 文章标题
- summary: 文章摘要（如果没有摘要则为空字符串）

请直接返回 JSON 格式，不要 markdown 代码块：
{
    "items": [
        {"url": "https://example.com/article1", "title": "标题1", "summary": "摘要1"},
        {"url": "https://example.com/article2", "title": "标题2", "summary": "摘要2"}
    ]
}

规则：
- 只提取主要文章内容，不要包含导航、广告、侧边栏等
- url 必须是完整的绝对 URL
- 如果某个字段不存在，用空字符串 ""
- items 始终是数组，即使只有一篇文章
"""

    def __init__(self):
        config = {
            "openai_api_key": settings.openai_api_key,
            "openai_base_url": settings.openai_base_url,
            "model": settings.model,
        }
        self._registry = LLMRegistry(config)

    def _get_llm(self):
        """获取默认 LLM 实例"""
        return self._registry.get(settings.model)

    def _strip_code_fences(self, content: str) -> str:
        """移除 markdown 代码块标记"""
        if "```" not in content:
            return content.strip()
        if "```json" in content:
            parts = content.split("```json")
            if len(parts) > 1:
                content = parts[1]
        else:
            parts = content.split("```")
            if len(parts) > 1:
                content = parts[1]
        return content.strip()

    def _extract_json_with_recovery(self, content: str) -> dict[str, Any]:
        """健壮的 JSON 解析，支持修复损坏的 JSON"""
        content = self._strip_code_fences(content)

        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 正则提取 JSON 块（从第一个 { 到最后一个 }）
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        logger.warning(f"JSON 解析失败，原始内容: {content[:200]}")
        return {}

    def extract_with_selectors(self, html: str, selectors: dict[str, str]) -> dict[str, Any]:
        """使用 CSS selectors 直接从 HTML 提取内容"""
        logger.info(f"[DOMExtractor.extract_with_selectors] HTML大小: {len(html)} bytes | selectors: {selectors}")
        soup = BeautifulSoup(html, "html.parser")
        result = {}

        for field, selector in selectors.items():
            try:
                elements = soup.select(selector)
                if not elements:
                    result[field] = ""
                    continue

                if field == "tags":
                    result[field] = [el.get_text(strip=True) for el in elements if el.get_text(strip=True)]
                elif field == "content":
                    # 合并多个元素内容
                    result[field] = "\n".join(el.get_text(separator="\n", strip=True) for el in elements)
                else:
                    result[field] = elements[0].get_text(strip=True)
            except Exception as e:
                logger.warning(f"Selector '{selector}' 提取失败: {e}")
                result[field] = ""

        logger.info(f"[DOMExtractor.extract_with_selectors] 提取完成 | title={bool(result.get('title'))} | author={bool(result.get('author'))} | content长度={len(result.get('content', ''))} | tags数量={len(result.get('tags', []))}")
        return result

    async def extract(self, html: str) -> dict[str, Any]:
        """使用 LLM 从 HTML 中提取结构化内容"""
        logger.info(f"[DOMExtractor.extract] LLM 提取开始 | HTML大小: {len(html)} bytes")
        llm = self._get_llm()
        html_preview = html[:15000] if len(html) > 15000 else html

        # 优先尝试 with_structured_output
        try:
            structured_llm = llm.with_structured_output(ExtractedContent)
            logger.info("[DOMExtractor.extract] 使用 with_structured_output")
            result = await structured_llm.ainvoke([
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=f"请提取以下 HTML 中的内容：\n\n{html_preview}"),
            ])
            result_dict = result.model_dump()
            logger.info(f"[DOMExtractor.extract] LLM 提取完成 | title={bool(result_dict.get('title'))} | content长度={len(result_dict.get('content', ''))}")
            return result_dict
        except Exception as e:
            logger.warning(f"with_structured_output 失败，尝试后备方案: {e}")

        # 后备方案：使用原始文本解析
        try:
            logger.info("[DOMExtractor.extract] 使用后备方案")
            response = await llm.ainvoke([
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=f"请提取以下 HTML 中的内容：\n\n{html_preview}"),
            ])
            result_dict = self._extract_json_with_recovery(response.content)
            logger.info(f"[DOMExtractor.extract] 后备方案完成 | title={bool(result_dict.get('title'))} | content长度={len(result_dict.get('content', ''))}")
            return result_dict
        except Exception as e:
            logger.error(f"LLM 提取失败: {e}")
            return {"title": "", "author": "", "published_at": "", "content": "", "tags": []}

    async def generate_selectors(self, html: str) -> dict[str, str]:
        """使用 LLM 分析 HTML 结构并生成 CSS selectors"""
        logger.info(f"[DOMExtractor.generate_selectors] LLM 生成 selectors | HTML大小: {len(html)} bytes")
        llm = self._get_llm()
        html_preview = html[:15000] if len(html) > 15000 else html

        # 优先尝试 with_structured_output
        try:
            structured_llm = llm.with_structured_output(DetailPageSelectors)
            logger.info("[DOMExtractor.generate_selectors] 使用 with_structured_output")
            result = await structured_llm.ainvoke([
                SystemMessage(content=self.SELECTOR_PROMPT),
                HumanMessage(content=f"请分析以下 HTML 结构并生成 selectors：\n\n{html_preview}"),
            ])
            result_dict = result.model_dump()
            logger.info(f"[DOMExtractor.generate_selectors] selectors 生成完成 | keys={list(result_dict.keys())}")
            return result_dict
        except Exception as e:
            logger.warning(f"with_structured_output 失败，尝试后备方案: {e}")

        # 后备方案
        try:
            logger.info("[DOMExtractor.generate_selectors] 使用后备方案")
            response = await llm.ainvoke([
                SystemMessage(content=self.SELECTOR_PROMPT),
                HumanMessage(content=f"请分析以下 HTML 结构并生成 selectors：\n\n{html_preview}"),
            ])
            result_dict = self._extract_json_with_recovery(response.content)
            logger.info(f"[DOMExtractor.generate_selectors] selectors 生成完成 | keys={list(result_dict.keys())}")
            return result_dict
        except Exception as e:
            logger.error(f"LLM selectors 生成失败: {e}")
            return {}

    def to_web_page_item(self, url: str, extracted: dict[str, Any], site_name: str = "") -> WebPageItem:
        """将从 DOM 提取的数据转换为 WebPageItem"""
        return WebPageItem(
            url=url,
            title=extracted.get("title", ""),
            author=extracted.get("author", ""),
            content=extracted.get("content", ""),
            tags=extracted.get("tags", []),
            published_at=None,
            site_name=site_name,
        )

    async def generate_list_item_selectors(self, html: str) -> dict[str, str]:
        """使用 LLM 分析列表页 HTML 结构并生成 CSS selectors"""
        llm = self._get_llm()
        html_preview = html[:15000] if len(html) > 15000 else html

        # 优先尝试 with_structured_output
        try:
            structured_llm = llm.with_structured_output(ListItemSelectors)
            logger.info("正在使用 with_structured_output 生成列表页 CSS selectors...")
            result = await structured_llm.ainvoke([
                SystemMessage(content=self.LIST_ITEM_SELECTOR_PROMPT),
                HumanMessage(content=f"请分析以下列表页 HTML 结构并生成 selectors：\n\n{html_preview}"),
            ])
            return result.model_dump()
        except Exception as e:
            logger.warning(f"with_structured_output 失败，尝试后备方案: {e}")

        # 后备方案
        try:
            logger.info("正在使用后备方案生成列表页 CSS selectors...")
            response = await llm.ainvoke([
                SystemMessage(content=self.LIST_ITEM_SELECTOR_PROMPT),
                HumanMessage(content=f"请分析以下列表页 HTML 结构并生成 selectors：\n\n{html_preview}"),
            ])
            return self._extract_json_with_recovery(response.content)
        except Exception as e:
            logger.error(f"LLM list selectors 生成失败: {e}")
            return {}

    async def extract_list_items(self, html: str) -> dict[str, Any]:
        """使用 LLM 从列表页 HTML 中提取所有文章条目信息"""
        llm = self._get_llm()
        html_preview = html[:15000] if len(html) > 15000 else html

        # 优先尝试 with_structured_output
        try:
            structured_llm = llm.with_structured_output(ListItemsResult)
            logger.info("正在使用 with_structured_output 提取列表页文章条目...")
            result = await structured_llm.ainvoke([
                SystemMessage(content=self.LIST_ITEM_EXTRACT_PROMPT),
                HumanMessage(content=f"请提取以下列表页 HTML 中的所有文章条目：\n\n{html_preview}"),
            ])
            return result.model_dump()
        except Exception as e:
            logger.warning(f"with_structured_output 失败，尝试后备方案: {e}")

        # 后备方案
        try:
            logger.info("正在使用后备方案提取列表页文章条目...")
            response = await llm.ainvoke([
                SystemMessage(content=self.LIST_ITEM_EXTRACT_PROMPT),
                HumanMessage(content=f"请提取以下列表页 HTML 中的所有文章条目：\n\n{html_preview}"),
            ])
            return self._extract_json_with_recovery(response.content)
        except Exception as e:
            logger.error(f"LLM list items 提取失败: {e}")
            return {"items": []}

    def extract_list_items_with_selectors(self, html: str, list_selectors: dict[str, str]) -> list[dict]:
        """使用 CSS selectors 从列表页 HTML 中提取所有文章条目信息"""
        logger.info(f"[DOMExtractor.extract_list_items_with_selectors] HTML大小: {len(html)} bytes | selectors: {list_selectors}")
        soup = BeautifulSoup(html, "html.parser")
        items = []

        item_container = list_selectors.get("item_container", "article")
        url_selector = list_selectors.get("url", "a[href]")
        title_selector = list_selectors.get("title", "h2, h3")
        summary_selector = list_selectors.get("summary", "p")

        # 查找所有文章条目容器
        containers = soup.select(item_container)
        logger.info(f"[DOMExtractor.extract_list_items_with_selectors] 找到 {len(containers)} 个容器")
        if not containers:
            logger.info("[DOMExtractor.extract_list_items_with_selectors] 未找到容器，返回空列表")
            return items

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
                items.append({
                    "url": url,
                    "title": title,
                    "summary": summary,
                })

        logger.info(f"[DOMExtractor.extract_list_items_with_selectors] 提取完成 | 提取到 {len(items)} 个条目")
        return items

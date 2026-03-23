import json
from typing import Any

from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from comp_synth.config import settings
from comp_synth.llm.registry import LLMRegistry
from comp_synth.schemas.web import WebPageItem


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

    def extract_with_selectors(self, html: str, selectors: dict[str, str]) -> dict[str, Any]:
        """使用 CSS selectors 直接从 HTML 提取内容"""
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

        return result

    async def extract(self, html: str) -> dict[str, Any]:
        """使用 LLM 从 HTML 中提取结构化内容"""
        llm = self._get_llm()

        # 截取 HTML 前面部分（避免过长）
        html_preview = html[:15000] if len(html) > 15000 else html

        logger.info("正在使用 LLM 提取 DOM 内容...")
        response = await llm.ainvoke([
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=f"请提取以下 HTML 中的内容：\n\n{html_preview}"),
        ])

        content = self._strip_code_fences(response.content)

        try:
            result = json.loads(content)
            return result
        except json.JSONDecodeError as e:
            logger.error(f"LLM 输出 JSON 解析失败: {e}")
            return {"title": "", "author": "", "published_at": "", "content": "", "tags": []}

    async def generate_selectors(self, html: str) -> dict[str, str]:
        """使用 LLM 分析 HTML 结构并生成 CSS selectors"""
        llm = self._get_llm()

        # 截取 HTML 前面部分
        html_preview = html[:15000] if len(html) > 15000 else html

        logger.info("正在使用 LLM 生成 CSS selectors...")
        response = await llm.ainvoke([
            SystemMessage(content=self.SELECTOR_PROMPT),
            HumanMessage(content=f"请分析以下 HTML 结构并生成 selectors：\n\n{html_preview}"),
        ])

        content = self._strip_code_fences(response.content)

        try:
            selectors = json.loads(content)
            return selectors
        except json.JSONDecodeError as e:
            logger.error(f"LLM selectors 输出 JSON 解析失败: {e}")
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

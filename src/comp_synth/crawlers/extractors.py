import json
import re
from typing import Any

from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel

from comp_synth.llm_provider.registry import llm_registry
from comp_synth.prompt import DOM_PROMPTS


class ListItemSelectors(BaseModel):
    """列表页 CSS Selectors"""
    item_container: str = ""
    url: str = ""
    title: str = ""
    summary: str = ""
    publish_date: str = ""


class DOMExtractor:
    """使用 LLM 从 HTML DOM 中提取结构化内容"""

    def __init__(self):
        self._llm = llm_registry.get()

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

    async def generate_list_item_selectors(self, html: str) -> dict[str, str]:
        """使用 LLM 分析列表页 HTML 结构并生成 CSS selectors"""
        llm = self._llm
        html_preview = html[:15000] if len(html) > 15000 else html

        # 优先尝试 with_structured_output
        try:
            structured_llm = llm.with_structured_output(ListItemSelectors)
            logger.info("正在使用 with_structured_output 生成列表页 CSS selectors...")
            result = await structured_llm.ainvoke([
                SystemMessage(content=DOM_PROMPTS["LIST_ITEM_SELECTOR"]),
                HumanMessage(content=f"请分析以下列表页 HTML 结构并生成 selectors：\n\n{html_preview}"),
            ])
            return result.model_dump()
        except Exception as e:
            logger.warning(f"with_structured_output 失败，尝试后备方案: {e}")

        # 后备方案
        try:
            logger.info("正在使用后备方案生成列表页 CSS selectors...")
            response = await llm.ainvoke([
                SystemMessage(content=DOM_PROMPTS["LIST_ITEM_SELECTOR"]),
                HumanMessage(content=f"请分析以下列表页 HTML 结构并生成 selectors：\n\n{html_preview}"),
            ])
            return self._extract_json_with_recovery(response.content)
        except Exception as e:
            logger.error(f"LLM list selectors 生成失败: {e}")
            return {}


    def extract_list_items_with_selectors(self, html: str, list_selectors: dict[str, str]) -> list[dict]:
        """使用 CSS selectors 从列表页 HTML 中提取所有文章条目信息"""
        logger.info(f"[DOMExtractor.extract_list_items_with_selectors] HTML大小: {len(html)} bytes | selectors: {list_selectors}")
        soup = BeautifulSoup(html, "html.parser")
        items = []

        item_container = list_selectors.get("item_container", "article")
        url_selector = list_selectors.get("url", "a[href]")
        title_selector = list_selectors.get("title", "h2, h3")
        summary_selector = list_selectors.get("summary", "p")
        publish_date_selector = list_selectors.get("publish_date", "span.date")

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

            publish_date = ""
            publish_date_elem = container.select_one(publish_date_selector)
            if publish_date_elem:
                publish_date = publish_date_elem.get_text(strip=True)

            if title and url:  # 至少需要标题和 URL
                items.append({
                    "url": url,
                    "title": title,
                    "summary": summary,
                    "publish_date": publish_date,
                })

        logger.info(f"[DOMExtractor.extract_list_items_with_selectors] 提取完成 | 提取到 {len(items)} 个条目")
        return items

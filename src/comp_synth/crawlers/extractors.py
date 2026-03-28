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


class DOMExtractor:
    """使用 LLM 从 HTML DOM 中提取结构化内容"""

    def __init__(self):
        self._llm = llm_registry.get()

    async def generate_list_item_selectors(self, html: str) -> List[dict[str, str]]:
        """使用 LLM 分析列表页 HTML 结构并生成 CSS selectors

        Returns:
            List[dict[str, str]]: CSS 选择器列表，每个 dict 包含一组选择器
                                例如: [{"item_container": "article", "url": "a", ...}, ...]
        """
        llm = self._llm
        html_preview = html[:15000] if len(html) > 15000 else html

        # 优先尝试 with_structured_output
        try:
            structured_llm = llm.with_structured_output(ListItemSelectors)
            logger.info("正在使用 with_structured_output 生成列表页 CSS selectors...")
            result: ListItemSelectors = await structured_llm.ainvoke([
                SystemMessage(content=DOM_PROMPTS["LIST_ITEM_SELECTOR"]),
                HumanMessage(content=f"请分析以下列表页 HTML 结构并生成 selectors：\n\n{html_preview}"),
            ])
            # 转换为 list[dict[str, str]]
            return [item.model_dump() for item in result.data]
        except Exception as e:
            logger.warning(f"with_structured_output 失败: {e}")
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
        logger.info(f"[DOMExtractor.extract_list_items_with_selectors] HTML大小: {len(html)} bytes | selectors列表长度: {len(list_selectors)}")
        soup = BeautifulSoup(html, "html.parser")
        all_items = []
        seen_urls: set[str] = set()

        for selector_idx, selectors in enumerate(list_selectors):
            logger.info(f"[DOMExtractor.extract_list_items_with_selectors] 正在使用第 {selector_idx + 1} 组选择器: {selectors}")

            item_container = selectors.get("item_container", "article")
            url_selector = selectors.get("url", "a[href]")
            title_selector = selectors.get("title", "h2, h3")
            summary_selector = selectors.get("summary", "p")

            # 查找所有文章条目容器
            containers = soup.select(item_container)
            logger.info(f"[DOMExtractor] 第 {selector_idx + 1} 组选择器找到 {len(containers)} 个容器")

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

        logger.info(f"[DOMExtractor.extract_list_items_with_selectors] 提取完成 | 提取到 {len(all_items)} 个条目（去重后）")
        return all_items

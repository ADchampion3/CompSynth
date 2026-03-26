import httpx
from readability import Document

from comp_synth.config import settings
from comp_synth.crawler.base import BaseCrawler
from comp_synth.schemas.web import WebPageItem


class WebCrawler(BaseCrawler):
    """普通网页爬虫，使用 httpx + readability 提取正文"""

    async def fetch(self, source_config: dict) -> list[WebPageItem]:
        url = source_config["url"]

        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.get(url)
            response.raise_for_status()

        doc = Document(response.text)

        item = WebPageItem(
            id=f"web:{url}",
            url=url,
            title=doc.short_title(),
            summary=doc.summary(),
            site_name=source_config.get("site_name", ""),
        )

        return [item]

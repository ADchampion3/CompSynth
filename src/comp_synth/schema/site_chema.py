from datetime import datetime

from pydantic import BaseModel, Field


class SiteSchema(BaseModel):
    """站点提取 Schema，用于缓存 CSS selectors 和 LLM 提取提示"""

    site_name: str = ""
    site_url: str = ""
    selectors: list[dict[str, str]] = Field(default_factory=list)
    # 列表页 CSS 选择器映射，支持多组选择器（针对同一页面的多个内容容器），例如:
    # [
    #     {
    #         "item_container": "article.post-item",
    #         "url": "a[href]",
    #         "title": "h2.title",
    #         "summary": "p.summary"
    #     },
    #     {
    #         "item_container": "div.article-section",
    #         "url": "a",
    #         "title": "h3",
    #         "summary": ".summary"
    #     }
    # ]
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    last_llm_call: datetime | None = None
    last_stale_refresh_call: datetime | None = None
    stale_refresh_count: int = 0

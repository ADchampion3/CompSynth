from datetime import datetime

from pydantic import BaseModel, Field


class SiteSchema(BaseModel):
    """站点提取 Schema，用于缓存 CSS selectors 和 LLM 提取提示"""

    site_name: str = ""
    site_url: str = ""
    selectors: dict[str, str] = Field(default_factory=dict)
    # CSS 选择器映射，例如:
    # {
    #     "title": "article h1.title",
    #     "author": ".author-name",
    #     "published_at": "time[datetime]",
    #     "content": "article .post-content",
    #     "tags": ".tags .tag"
    # }
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    last_llm_call: datetime | None = None

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

ArticleTag = Literal["技术博客", "比赛信息", "就业招聘", "技术发布", "其他"]

ALL_TAGS: list[ArticleTag] = ["技术博客", "比赛信息", "就业招聘", "技术发布", "其他"]


class ContentItem(BaseModel):
    """内容项基础模型，所有信息源的结构化输出"""

    source: str
    url: str
    title: str = ""
    summary: str = ""
    content: str = ""
    tags: list[str] = Field(default_factory=lambda: ["其他"])
    published_at: datetime | None = None
    collected_at: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)

    @computed_field
    @property
    def id(self) -> str:
        return f"{self.source}:{self.url}"


class RSSItem(ContentItem):
    """RSS/Atom 订阅内容项"""

    source: str = "rss"


class WebPageItem(ContentItem):
    """普通网页内容项"""

    source: str = "web"

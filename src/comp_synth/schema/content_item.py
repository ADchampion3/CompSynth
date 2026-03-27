from datetime import datetime

from pydantic import BaseModel, Field


class ContentItem(BaseModel):
    """内容项基础模型，所有信息源的结构化输出"""

    source: str
    url: str
    title: str = ""
    summary: str = ""
    content: str = ""
    published_at: datetime | None = None
    collected_at: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)


class RSSItem(ContentItem):
    """RSS/Atom 订阅内容项"""

    source: str = "rss"

    @property
    def id(self):
        return f"{self.source}:{self.url}"


class WebPageItem(ContentItem):
    """普通网页内容项"""

    source: str = "web"

    @property
    def id(self):
        return f"{self.source}:{self.url}"

import hashlib
from datetime import datetime

from pydantic import BaseModel, Field


class ContentItem(BaseModel):
    """内容项基础模型，所有信息源的结构化输出"""

    source: str
    url: str
    title: str = ""
    summary: str = ""
    content: str
    published_at: datetime | None = None
    collected_at: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)
    content_hash: str = ""

    def model_post_init(self, __context) -> None:
        if self.content and not self.content_hash:
            self.content_hash = hashlib.sha256(
                self.content.encode("utf-8")
            ).hexdigest()

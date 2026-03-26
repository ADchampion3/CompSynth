from datetime import datetime

from pydantic import BaseModel, Field


class ContentItem(BaseModel):
    """内容项基础模型，所有信息源的结构化输出"""

    id: str  # Primary identifier, format: "{source}:{url}"
    source: str
    url: str
    title: str = ""
    summary: str = ""
    published_at: datetime | None = None
    collected_at: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)
    vector_id: str = ""  # ChromaDB internal ID

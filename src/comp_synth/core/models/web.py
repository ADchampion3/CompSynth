
from pydantic import Field

from comp_synth.core.models.base import ContentItem


class WebPageItem(ContentItem):
    """普通网页内容项"""

    source: str = "web"
    description: str = ""
    site_name: str = ""
    author: str = ""
    tags: list[str] = Field(default_factory=list)

    @property
    def id(self):
        return f"{self.source}:{self.url}"

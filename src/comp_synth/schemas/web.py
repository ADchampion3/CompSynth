
from typing import Any

from comp_synth.schemas.base import ContentItem


class WebPageItem(ContentItem):
    """普通网页内容项"""

    source: str = "web"
    author: str = ""
    tags: list[str] = []
    site_name: str = ""
    metadata: dict[str, Any] = {}

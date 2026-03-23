
from comp_synth.schemas.base import ContentItem


class RSSItem(ContentItem):
    """RSS/Atom 订阅内容项"""

    source: str = "rss"
    feed_url: str

    @property
    def id(self):
        return f"{self.source}:{self.url}"

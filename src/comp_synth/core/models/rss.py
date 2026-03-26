
from comp_synth.core.models.base import ContentItem


class RSSItem(ContentItem):
    """RSS/Atom 订阅内容项"""

    source: str = "rss"
    feed_url: str

    @property
    def id(self):
        return f"{self.source}:{self.url}"

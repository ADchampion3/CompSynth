from comp_synth.schemas.base import ContentItem


class WebPageItem(ContentItem):
    """普通网页内容项"""

    source: str = "web"
    description: str = ""
    site_name: str = ""

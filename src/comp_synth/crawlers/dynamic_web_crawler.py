from comp_synth.crawlers.adaptive_web_crawler import AdaptiveWebCrawler
from comp_synth.crawlers.base import BaseCrawler
from comp_synth.schema.content_item import WebPageItem
from comp_synth.store.crawl_tracker import CrawlTracker

SPA_MARKERS = [
    "__NEXT_DATA__",
    "__NUXT_DATA__",
    "data-vue-app",
    "ng-app",
    "data-reactroot",
    "__SVELTEKIT",
    "data-remix-context",
]


def is_likely_spa(html: str) -> bool:
    """检测是否可能是 SPA（内容过短或包含 SPA 框架标记）"""
    if len(html) < 200:
        return True
    for marker in SPA_MARKERS:
        if marker in html:
            return True
    return False


class DynamicWebCrawler(BaseCrawler):
    """
    支持 JavaScript 动态渲染的网页爬虫。

    策略：
      1. 先用 httpx 获取 HTML
      2. 检测是否为 SPA（HTML 过短或包含 SPA 标记）
      3. 若检测到 SPA 或 javascript:true 配置，切换 DrissionPage Chrome 渲染
      4. 委托 AdaptiveWebCrawler 处理内容提取（列表页/详情页检测）
    """

    def __init__(self):
        self._tracker = CrawlTracker()
        self._delegate = AdaptiveWebCrawler()

    async def fetch_page(
        self, url: str, user_selectors: list[dict[str, str]] | None = None
    ) -> list[WebPageItem]:
        """
        从单个页面抓取内容（支持 JavaScript 渲染）。

        流程：
        1. 获取 HTML（httpx 或 Chrome 渲染）
        2. 检测页面类型：列表页 vs 详情页
        3. 委托 AdaptiveWebCrawler 提取
        """
        # 先尝试 httpx
        html = ""
        try:
            html = await self._fetch_html(url)
        except Exception:
            pass

        # 检测是否需要 JS 渲染
        if is_likely_spa(html):
            html = await self._fetch_html_with_browser(url)

        # 检测页面类型，委托给 AdaptiveWebCrawler
        if self._delegate._is_list_page(html):
            return await self._delegate._crawl_list_page(html, url, user_selectors)
        else:
            return await self._delegate._crawl_detail_page(html, url)

    async def fetch(
        self, source_config: dict, user_selectors: list[dict[str, str]] | None = None
    ) -> list[WebPageItem]:
        """
        兼容接口，内部委托给 fetch_page。

        支持 source_config 中的 javascript:true 配置强制使用浏览器渲染。
        """
        url = source_config["url"]
        force_js = source_config.get("javascript", False)

        # 先尝试 httpx
        html = ""
        try:
            html = await self._fetch_html(url)
        except Exception:
            pass

        # 强制 JS 渲染或检测到 SPA
        if force_js or is_likely_spa(html):
            html = await self._fetch_html_with_browser(url)

        # 检测页面类型，委托给 AdaptiveWebCrawler
        if self._delegate._is_list_page(html):
            return await self._delegate._crawl_list_page(html, url, user_selectors)
        else:
            return await self._delegate._crawl_detail_page(html, url)

    async def maybe_fetch_detail(self, item: WebPageItem, site_name: str) -> WebPageItem | None:
        """委托给 AdaptiveWebCrawler 处理详情页获取"""
        return await self._delegate.maybe_fetch_detail(item, site_name)

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
      4. 委托 AdaptiveWebCrawler 处理内容提取
    """

    def __init__(self):
        self._tracker = CrawlTracker()
        self._delegate = AdaptiveWebCrawler()

    def _fetch_with_chrome(self, url: str) -> str:
        """使用 DrissionPage Chrome 渲染获取 HTML"""
        from DrissionPage import ChromiumPage

        page = ChromiumPage()
        page.get(url, timeout=30)
        html = page.html
        page.quit()
        return html

    async def fetch(
        self, source_config: dict, user_selectors: list[dict[str, str]] | None = None
    ) -> list[WebPageItem]:
        url = source_config["url"]

        # 先尝试 httpx
        html = ""
        try:
            html = await self._fetch_html(url)
        except Exception:
            pass

        # 检测是否需要 JS 渲染
        force_js = source_config.get("javascript", False)
        if force_js or is_likely_spa(html):
            html = self._fetch_with_chrome(url)

        # 委托 AdaptiveWebCrawler 提取
        return await self._delegate._crawl_detail_page(html, url)

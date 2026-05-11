# Crawlee Python Integration Guide

> Integration reference for replacing CompSynth's HTTP/JS fetching layer with Crawlee.
> See `docs/crawlee-plan.md` for migration strategy and decisions.

---

## Table of Contents

1. [Installation](#installation)
2. [Crawler Types Compared](#crawler-types-compared)
3. [Router and Labels](#router-and-labels)
4. [Content Extraction](#content-extraction)
5. [Data Output](#data-output)
6. [Session Management](#session-management)
7. [Proxy Configuration](#proxy-configuration)
8. [Anti-Blocking](#anti-blocking)
9. [Error Handling](#error-handling)
10. [Storage Clients](#storage-clients)
11. [CompSynth Integration](#compsynth-integration)
12. [Hidden Pitfalls](#hidden-pitfalls)
13. [DrissionPage vs Playwright](#drissionpage-vs-playwright)
14. [Resources](#resources)

---

## Installation

```bash
# Core (HTTP-only, no JS)
pip install crawlee

# BeautifulSoup support (static HTML sites)
pip install crawlee[beautifulsoup]

# Playwright support (JavaScript sites)
pip install crawlee[playwright]
playwright install chromium  # Must run separately after install
```

The `BeautifulSoupCrawler` and `PlaywrightCrawler` are in `crawlee.crawlers` (not `crawlee.bs` or `crawlee.playwright`):

```python
from crawlee.crawlers import BeautifulSoupCrawler, PlaywrightCrawler, BeautifulSoupCrawlingContext, PlaywrightCrawlingContext
```

---

## Crawler Types Compared

| Crawler | JS Rendering | Speed | Use Case |
|---------|-------------|-------|----------|
| `BeautifulSoupCrawler` | No | Fast (HTTP) | Static blogs, RSS, API pages |
| `PlaywrightCrawler` | Yes | Slow (browser) | SPAs, client-side rendered sites |
| `ParselCrawler` | No | Fast (HTTP) | Sites needing XPath + CSS selectors |

**CompSynth mapping:**
- `AdaptiveWebCrawler` (HTTP, non-JS) → `BeautifulSoupCrawler`
- `DynamicWebCrawler` (JS, DrissionPage) → `PlaywrightCrawler`

### BeautifulSoupCrawler

```python
from datetime import timedelta
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext

crawler = BeautifulSoupCrawler(
    max_request_retries=3,
    request_handler_timeout=timedelta(seconds=30),
    max_requests_per_crawl=100,
    max_concurrent_requests=10,
)

@crawler.router.default_handler
async def handler(context: BeautifulSoupCrawlingContext) -> None:
    context.log.info(f'Fetching {context.request.url}')

    # BeautifulSoup available as context.soup
    title = context.soup.title.string if context.soup.title else None

    # Push extracted data to default dataset
    await context.push_data({
        'url': context.request.url,
        'title': title,
    })

    # Enqueue discovered links (respects max_requests_per_crawl)
    await context.enqueue_links()
```

### PlaywrightCrawler

```python
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

crawler = PlaywrightCrawler(
    headless=True,
    browser_type='chromium',  # 'chromium' | 'firefox' | 'webkit'
    max_requests_per_crawl=50,
)

@crawler.router.default_handler
async def handler(context: PlaywrightCrawlingContext) -> None:
    # Wait for content to render
    await context.page.wait_for_load_state('networkidle')

    # Playwright page API
    title = await context.page.title()

    await context.push_data({'url': context.request.url, 'title': title})
    await context.enqueue_links()
```

---

## Router and Labels

The router maps incoming requests to handlers by label. This replaces `AdaptiveWebCrawler._is_list_page()` logic.

### Label-Based Routing

```python
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext

crawler = BeautifulSoupCrawler()

# Label a page as LIST when enqueueing links
@crawler.router.default_handler
async def default_handler(context: BeautifulSoupCrawlingContext) -> None:
    await context.enqueue_links(selector='.article-item a', label='LIST')

# Dedicated list page handler
@crawler.router.handler('LIST')
async def list_handler(context: BeautifulSoupCrawlingContext) -> None:
    items = context.soup.select('.article-item')
    for item in items:
        await context.push_data({
            'title': item.select_one('h2').get_text(strip=True) if item.select_one('h2') else None,
            'url': item.select_one('a')['href'] if item.select_one('a') else None,
        })
    # Continue crawling links found within the list items
    await context.enqueue_links(selector='.article-item a')

# Detail page handler (unlabeled fallback)
@crawler.router.handler('DETAIL')  # or use default_handler for unlabeled
async def detail_handler(context: BeautifulSoupCrawlingContext) -> None:
    title = context.soup.select_one('h1').get_text(strip=True)
    content = context.soup.select_one('article').get_text(strip=True) if context.soup.select_one('article') else ''
    await context.push_data({'title': title, 'content': content})
```

### How Labels Work

- `enqueue_links(label='PAGE_TYPE')` — assigns a label to discovered URLs
- `crawler.router.handler('PAGE_TYPE')` — handles all URLs with that label
- `crawler.router.default_handler` — handles URLs with no label (fallback)
- Labels persist through the crawl queue

---

## Content Extraction

### BeautifulSoup (BeautifulSoupCrawler)

```python
# context.soup is a BeautifulSoup object
soup = context.soup

# CSS selectors
title = soup.select_one('h1.article-title')
items = soup.select('article.post-item')

# Find with attributes
link = soup.select_one('a[href*="/article/"]')

# Text extraction
text = title.get_text(separator='\n', strip=True) if title else ''
```

### Playwright (PlaywrightCrawler)

```python
page = context.page

# locator API (preferred — modern Playwright)
title = await page.locator('h1.article-title').text_content()
items = page.locator('article.post-item')

# Wait for element to appear
await page.wait_for_selector('.article-title', timeout=5000)

# query_selector (returns ElementHandle — older API)
element = await page.query_selector('.article-title')
text = await element.inner_text() if element else None

# query_selector_all
elements = await page.query_selector_all('.article-item a')
for el in elements:
    href = await el.get_attribute('href')

# Wait for load state instead of selector (often more reliable)
await page.wait_for_load_state('networkidle')

# Wait for function
await page.wait_for_function("document.querySelectorAll('.article-item').length > 0")

# Evaluate JS in page context
result = await page.evaluate("""
    () => {
        const items = document.querySelectorAll('.article-item');
        return Array.from(items).map(i => ({
            title: i.querySelector('h2')?.innerText,
            url: i.querySelector('a')?.href
        }));
    }
""")
```

### XPath Support

```python
# Via Playwright locator (xpath= prefix)
elements = page.locator('xpath=//article[@class="post-item"]')

# Via BeautifulSoup (lxml parser required)
soup = BeautifulSoup(html, 'lxml')
items = soup.select('//article[@class="post-item"]')  # CSS-like
items = soup.find_all('article', class_='post-item')  # Native BS4
```

---

## Data Output

### push_data

```python
await context.push_data({'url': context.request.url, 'title': '...'})

# List of dicts in one call
await context.push_data([
    {'url': 'https://example.com/1', 'title': 'First'},
    {'url': 'https://example.com/2', 'title': 'Second'},
])
```

### Export Results

```python
# Export entire dataset to JSON (default)
await crawler.export_data('results.json')

# Export to CSV
await crawler.export_data('results.csv', to_csv=True)

# Access dataset directly (for programmatic use)
dataset = await crawler.get_dataset()
items = await dataset.get_items()
```

### Request Metadata

```python
# Access the original request object
url = context.request.url
method = context.request.method
headers = context.request.headers

# User data passed via Request
from crawlee.models import Request

request = Request(
    url='https://example.com',
    user_data={'site_name': 'example', 'selectors': {...}},
)
await crawler.run([request])

# Access in handler
site_name = context.request.user_data.get('site_name')
selectors = context.request.user_data.get('selectors')
```

---

## Session Management

### SessionPool Configuration

```python
from datetime import timedelta
from crawlee.sessions import SessionPool

session_pool = SessionPool(
    max_pool_size=100,
    create_session_settings={
        'max_age': timedelta(minutes=50),
        'max_error_score': 3.0,           # Session marked unusable at this score
        'error_score_decrement': 0.5,      # Decrement on success
        'max_usage_count': 50,             # Max requests per session
        'blocked_status_codes': [401, 403, 429],
    },
    persistence_enabled=False,  # Disable for containerized/ephemeral infra
)

crawler = BeautifulSoupCrawler(
    session_pool=session_pool,
    max_session_rotations=5,  # Rotate after N consecutive blocked requests
)
```

### Manual Session Control

```python
@crawler.router.default_handler
async def handler(context):
    # context.session is available
    session = context.session

    if session is None:
        return  # Session pool not configured

    # Mark success (decrements error_score)
    session.mark_good_request()

    # Mark failure with status code (increments error_score)
    session.mark_bad_request(status_code=403)

    # Check if session is still usable
    if not session.is_usable():
        await crawler.session_pool.retire_session(session)

    # Access session metadata
    session_id = session.id
    usage_count = session.usage_count
    error_score = session.error_score
```

### Session Persistence

Sessions persist to disk by default (`~/.crawlee/sessions/`). For ephemeral infra:

```python
session_pool = SessionPool(persistence_enabled=False)
```

---

## Proxy Configuration

### Tiered Proxy

```python
from crawlee import ProxyConfiguration

proxy_config = ProxyConfiguration({
    'proxy_urls': [
        'http://user:pass@proxy-tier-1.com:8080',
        'http://user:pass@proxy-tier-2.com:8080',
    ],
    # Remaining URLs are fallback if above fail
})

crawler = BeautifulSoupCrawler(proxy_configuration=proxy_config)
```

### Playwright-Specific Proxy

```python
crawler = PlaywrightCrawler(
    proxy_configuration=proxy_config,
    browser_type='chromium',
)
```

---

## Anti-Blocking

### Browser Fingerprint Customization (PlaywrightCrawler)

```python
from crawlee.playwright import DefaultFingerprintGenerator, HeaderGeneratorOptions, ScreenOptions

crawler = PlaywrightCrawler(
    playwright_options={
        'fingerprint_generator': DefaultFingerprintGenerator(
            header_generator_options=HeaderGeneratorOptions(
                locales=['en-US', 'en', 'zh-CN'],
                operating_systems=['windows', 'linux'],
                browsers=['chrome'],
            ),
            screen_options=ScreenOptions(
                min_screen_width=1024,
                max_screen_width=1920,
                min_screen_height=768,
                max_screen_height=1080,
            ),
        ),
    }
)
```

### Block Unnecessary Resources (PlaywrightCrawler)

```python
from crawlee.playwright_crawler.block_requests import block_requests

BLOCKED_PATTERNS = [
    '.css', '.woff', '.woff2', '.font',
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico',
    '.pdf', '.zip', '.tar', '.gz',
    'google-analytics.com', 'doubleclick.net',
    'googlesyndication.com', 'googleadservices.com',
    'cdn.coil.com',  # unnecessary resource patterns
]

async def setup_page(page):
    # Block resource loading for performance
    await page.route(
        lambda url: any(p in str(url) for p in BLOCKED_PATTERNS),
        lambda route: route.abort(),
    )

@crawler.router.default_handler
async def handler(context):
    await setup_page(context.page)
    # ... rest of handler
```

### Pre-Navigation Hook (PlaywrightCrawler)

```python
@crawler.pre_navigation_hook
async def before_navigation(context) -> None:
    # Set custom headers
    await context.page.set_extra_http_headers({
        'Accept-Language': 'en-US,en;q=0.9',
        'X-Custom-Header': 'value',
    })

    # Modify cookies before navigation
    await context.page.context.add_cookies([{
        'name': 'session_id',
        'value': 'abc123',
        'domain': '.example.com',
        'path': '/',
    }])
```

---

## Error Handling

### Failed Request Handler (after all retries exhausted)

```python
from crawlee import RequestHandler

class CustomRequestHandler(RequestHandler):
    async def failed_request_handler(self, context):
        status = context.response.status_code if context.response else None

        if status in [500, 502, 503, 504]:
            # Retryable server error — re-enqueue
            self.log.info(f'Retrying {context.request.url} after server error')
            await context.enqueue_request(context.request.url)
        else:
            # Non-retryable — log and skip
            self.log.warning(
                f'Crawl failed permanently: {context.request.url} '
                f'status={status} error={context.error_message}'
            )
```

### Error Handler (exception during processing, before retry)

```python
    async def error_handler(self, context):
        # Non-network errors (parsing, logic) — don't retry
        if not isinstance(context.error, (ConnectionError, TimeoutError)):
            self.log.error(f'Non-retryable error on {context.request.url}: {context.error}')
            return  # Skip, don't retry

        # Network errors — let Crawlee retry normally
        await super().error_handler(context)
```

### Playwright Timeout Handling

```python
from playwright.async_api import TimeoutError as PlaywrightTimeout

async def safe_wait(selector, page, timeout=5000):
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        return True
    except PlaywrightTimeout:
        return False

@crawler.router.default_handler
async def handler(context):
    if not await safe_wait('.article-content', context.page):
        context.log.warning(f'Selector not found on {context.request.url}')
```

---

## Storage Clients

Crawlee uses storage clients to persist datasets, request queues, and sessions.

### MemoryStorageClient (default, non-persistent)

```python
from crawlee.storage import MemoryStorageClient

crawler = BeautifulSoupCrawler(storage_client=MemoryStorageClient())
# Data lost after crawl — useful for testing
```

### FileStorageClient (persistent)

```python
from crawlee.storage import FileStorageClient

crawler = BeautifulSoupCrawler(
    storage_client=FileStorageClient(
        persist_directory='.crawlee/data',
    )
)
# Persists to .crawlee/ directory — default location
```

### Dataset Access

```python
# Access default dataset
dataset = await crawler.get_dataset()
items = await dataset.get_items()
count = await dataset.get_count()

# Push to a named dataset
from crawlee.storage import FileStorageClient
from crawlee.datasets import Dataset

storage = FileStorageClient(persist_directory='.crawlee/data')
dataset = Dataset(storage_client=storage, id='my-dataset')
await dataset.push_items([{'url': 'https://example.com', 'title': 'Example'}])
```

---

## CompSynth Integration

### Architecture Decision

Replace `BaseCrawler._fetch_html` (httpx + tenacity) and `BaseCrawler._fetch_html_with_browser` (DrissionPage) with Crawlee. Keep:
- `DOMExtractor.extract_list_items_with_selectors()` — CSS selector extraction
- `DOMExtractor.generate_list_item_selectors()` — LLM-based selector learning
- `SchemaStore` — selector persistence with LLM rate limiting

### Integration Pattern

```python
# src/crawlers/crawlee_crawler.py

from crawlee.crawlers import BeautifulSoupCrawler, PlaywrightCrawler
from crawlee.crawlers import BeautifulSoupCrawlingContext, PlaywrightCrawlingContext
from crawlee.sessions import SessionPool
from datetime import timedelta
from typing import Protocol

from comp_synth.crawlers.extractors import DOMExtractor
from comp_synth.store.schema_store import SchemaStore
from comp_synth.schema.content_item import WebPageItem


def create_bs_crawler(site_name: str, site_config: dict) -> BeautifulSoupCrawler:
    """Create a BeautifulSoupCrawler wired to CompSynth's extraction pipeline."""
    crawler = BeautifulSoupCrawler(
        max_request_retries=3,
        request_handler_timeout=timedelta(seconds=30),
        max_requests_per_crawl=site_config.get('max_requests', 100),
    )

    @crawler.router.default_handler
    async def handler(context: BeautifulSoupCrawlingContext) -> None:
        # Pass site-specific selectors from SchemaStore
        schema = SchemaStore().get(site_name)
        selectors = schema.selectors if schema else None

        items = []
        if selectors:
            items = DOMExtractor().extract_list_items_with_selectors(
                str(context.soup), selectors
            )

        for item in items:
            await context.push_data({
                'url': item.get('url'),
                'title': item.get('title'),
                'summary': item.get('summary'),
                'site_name': site_name,
            })

        # Continue crawling list item links
        await context.enqueue_links(selector='a[href]')

    return crawler


def create_playwright_crawler(site_name: str, site_config: dict) -> PlaywrightCrawler:
    """Create a PlaywrightCrawler for JS-heavy sites."""
    crawler = PlaywrightCrawler(
        headless=True,
        browser_type='chromium',
        max_requests_per_crawl=site_config.get('max_requests', 50),
    )

    @crawler.router.default_handler
    async def handler(context: PlaywrightCrawlingContext) -> None:
        await context.page.wait_for_load_state('networkidle')

        schema = SchemaStore().get(site_name)
        selectors = schema.selectors if schema else None

        if selectors:
            # Extract using DOMExtractor on rendered HTML
            html = await context.page.content()
            items = DOMExtractor().extract_list_items_with_selectors(html, selectors)

            for item in items:
                await context.push_data({
                    'url': item.get('url'),
                    'title': item.get('title'),
                    'site_name': site_name,
                })

        await context.enqueue_links(selector='a[href]')

    return crawler
```

### CrawlTracker Dedup → Crawlee Dedup

Current `CrawlTracker` uses SQLite to track crawled URLs. Crawlee deduplicates via request fingerprints (URL + method). Migration path:

```python
# Phase 1: Run in parallel — Crawlee dedup + CrawlTracker preserved
# Phase 2: Validate Crawlee dedup covers all cases
# Phase 3: Remove CrawlTracker dependency

# To enable Crawlee's built-in request deduplication:
crawler = BeautifulSoupCrawler(
    request_deduplication=True,  # Default: True
)
```

---

## Hidden Pitfalls

### 1. Install the correct extra

```bash
pip install crawlee[beautifulsoup]  # Not just `pip install crawlee`
pip install crawlee[playwright]      # For PlaywrightCrawler
playwright install chromium           # Browsers not included
```

### 2. Session pool persistence in containers

```python
# Default: persists to ~/.crawlee/sessions/
# In Docker/ephemeral infra → sessions lost on restart
session_pool = SessionPool(persistence_enabled=False)
```

### 3. MemoryStorageClient loses data between runs

```python
# Default in some configurations — no data persists
crawler = BeautifulSoupCrawler(
    storage_client=FileStorageClient(persist_directory='.crawlee/data')
)
```

### 4. `query_selector` returns ElementHandle, not text

```python
# WRONG
text = await context.page.query_selector('.title').text_content()  # AttributeError

# CORRECT
el = await context.page.query_selector('.title')
text = await el.inner_text() if el else None

# PREFERRED — locator API
text = await context.page.locator('.title').text_content()
```

### 5. `wait_for_selector` raises on timeout

```python
# WRONG — timeout raises PlaywrightTimeout, breaking the handler
await context.page.wait_for_selector('.content', timeout=5000)

# CORRECT — wrap in try/except
from playwright.async_api import TimeoutError
try:
    await context.page.wait_for_selector('.content', timeout=5000)
except TimeoutError:
    context.log.warning('Selector .content not found')
```

### 6. `enqueue_links()` respects `max_requests_per_crawl`

```python
# Setting max_requests_per_crawl too low stops deep crawls early
crawler = BeautifulSoupCrawler(max_requests_per_crawl=20)
# After 20 requests, enqueue_links() queues nothing new
```

### 7. Cookies don't persist across crawler restarts

```python
# Sessions handle cookie state, but you must reuse the SAME session_pool
# Create once, reuse across crawler runs
session_pool = SessionPool(...)  # Create outside the crawl loop
```

### 8. Browser crashes with high concurrency

```python
# Limit concurrent pages to avoid browser instability
crawler = PlaywrightCrawler(max_concurrent_pages=3)
```

### 9. `run()` accepts Request objects, not just URLs

```python
from crawlee.models import Request

# WRONG
await crawler.run(['https://example.com'])

# CORRECT — with user_data for selector passing
request = Request(
    url='https://example.com',
    user_data={'site_name': 'example', 'selectors': [...], 'max_requests': 50},
)
await crawler.run([request])
```

### 10. DrissionPage and Playwright handle cookies differently

DrissionPage stores cookies per-domain by default. Playwright uses a `context` (browser context) that holds cookies. When migrating `DynamicWebCrawler`:
- DrissionPage: `page.cookies()` / `page.set.cookies()`
- Playwright: `page.context.cookies()` / `page.context.add_cookies()`

---

## DrissionPage vs Playwright

`DynamicWebCrawler` currently uses DrissionPage (a Chinese-developed browser automation library). Playwright is more widely used but has some differences:

| Feature | DrissionPage | Playwright |
|---------|-------------|------------|
| Browser support | Chromium-only | Chromium/Firefox/WebKit |
| Cookie storage | Per-domain, automatic | Manual via context |
| Page.wait() | `page.wait(n)` (seconds) | `page.wait_for_timeout(ms)` |
| Community | Smaller | Large, well-documented |
| CompSynth current use | Yes (`_fetch_html_with_browser`) | Planned replacement |

### Equivalent Operations

```python
# DrissionPage (current)
page.get(url)
page.wait(2)  # Wait 2 seconds
cookies = page.cookies()
page.set.cookies(cookies)

# Playwright (Crawlee)
page.goto(url)
await page.wait_for_timeout(2000)
cookies = page.context.cookies()
await page.context.add_cookies(cookies)
```

### Playwright wait methods

```python
# Wait for network to be idle (often better than fixed wait)
await page.wait_for_load_state('networkidle')

# Wait for specific selector
await page.wait_for_selector('.content', timeout=5000)

# Wait for JS condition
await page.wait_for_function("document.querySelector('.content') !== null")

# Wait for navigation
await page.wait_for_url('**/article/*')
```

---

## Resources

- [Crawlee Python Docs](https://crawlee.dev/python)
- [BeautifulSoupCrawler Guide](https://github.com/apify/crawlee-python/blob/master/docs/introduction/02_first_crawler.mdx)
- [PlaywrightCrawler Guide](https://github.com/apify/crawlee-python/blob/master/README.md)
- [Anti-Blocking Guide](https://github.com/apify/crawlee-python/blob/master/docs/guides/avoid_blocking.mdx)
- [Proxy Management](https://github.com/apify/crawlee-python/blob/master/docs/guides/proxy_management.mdx)
- [Session Management](https://github.com/apify/crawlee-python/blob/master/docs/guides/request_router.mdx)
- [Error Handling](https://github.com/apify/crawlee-python/blob/master/docs/guides/error_handling.mdx)
- [Storage Clients](https://github.com/apify/crawlee-python/blob/master/docs/guides/storage_clients.mdx)

"""Test HTML preprocessing pipeline.

Runs outside pytest — call directly:
    uv run python scripts/test_preprocessing.py <url>
    uv run python scripts/test_preprocessing.py https://example.com/blog

Shows detailed step-by-step cleaning process and final selector output.
"""

import asyncio
import sys
import time

import httpx
from bs4 import BeautifulSoup

from comp_synth.crawlers.extractors import DOMExtractor


def separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def size_report(label: str, before: str, after: str) -> None:
    ratio = len(after) / len(before) * 100 if before else 0
    reduction = 100 - ratio
    print(f"  [{label}] {len(before):>8} → {len(after):>8} chars  ({reduction:+.1f}%)")


def count_elements(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    return len(soup.find_all(True))


def count_report(label: str, before: str, after: str) -> None:
    before_n = count_elements(before)
    after_n = count_elements(after)
    removed = before_n - after_n
    print(f"  [{label}] {before_n:>5} → {after_n:>5} elements  (removed {removed})")


def list_removed_elements(before_soup, after_soup, label: str) -> None:
    """List element types that were removed."""
    before_tags = {}
    for el in before_soup.find_all(True):
        before_tags[el.name] = before_tags.get(el.name, 0) + 1
    after_tags = {}
    for el in after_soup.find_all(True):
        after_tags[el.name] = after_tags.get(el.name, 0) + 1

    removed = []
    for tag, count in before_tags.items():
        after_count = after_tags.get(tag, 0)
        diff = count - after_count
        if diff > 0:
            removed.append(f"{tag}(-{diff})")

    if removed:
        print(f"  [{label}] removed: {', '.join(removed)}")


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/test_preprocessing.py <url>")
        print("Example: uv run python scripts/test_preprocessing.py https://example.com/blog")
        sys.exit(1)

    url = sys.argv[1]
    print(f"Target URL: {url}")

    # ── Fetch HTML ──
    separator("Fetching HTML")
    t0 = time.time()
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; CompSynth/1.0)"})
        resp.raise_for_status()
    raw_html = resp.text
    fetch_time = time.time() - t0
    print(f"  Status: {resp.status_code}")
    print(f"  Size:   {len(raw_html):,} chars")
    print(f"  Time:   {fetch_time:.2f}s")
    print(f"  Elements: {count_elements(raw_html)}")

    extractor = DOMExtractor()
    original_html = raw_html

    # ── Layer 0: _preprocess_html_soup ──
    separator("Layer 0: _preprocess_html_soup (noise tags, on*/data-* attrs, noise classes)")
    soup0 = BeautifulSoup(raw_html, "html.parser")
    soup0_before = str(soup0)

    # Show what noise tags exist
    noise_tags = ["script", "style", "nav", "footer", "header", "noscript",
                  "iframe", "svg", "img", "input", "button", "link", "meta",
                  "head", "audio", "video", "canvas"]
    found_noise = {}
    for tag in soup0.find_all(noise_tags):
        found_noise[tag.name] = found_noise.get(tag.name, 0) + 1
    if found_noise:
        print(f"  Noise tags found: {found_noise}")

    # Show on* and data-* attrs
    on_attrs = 0
    data_attrs = 0
    for el in soup0.find_all(True):
        for attr in (el.attrs or {}):
            if attr.startswith("on"):
                on_attrs += 1
            elif attr.startswith("data-"):
                data_attrs += 1
    print(f"  on* attributes: {on_attrs}")
    print(f"  data-* attributes: {data_attrs}")

    t0 = time.time()
    soup0 = extractor._preprocess_html_soup(soup0)
    layer0_html = str(soup0)
    layer0_time = time.time() - t0

    size_report("Layer 0", soup0_before, layer0_html)
    count_report("Layer 0", soup0_before, layer0_html)
    list_removed_elements(
        BeautifulSoup(soup0_before, "html.parser"),
        BeautifulSoup(layer0_html, "html.parser"),
        "Layer 0"
    )
    print(f"  Time: {layer0_time:.3f}s")

    # ── Layer 1: _deep_clean ──
    separator("Layer 1: _deep_clean (ads, social, cookie, comments, related, sidebar, hidden)")
    soup1 = BeautifulSoup(layer0_html, "html.parser")

    # Show what noise patterns exist before cleaning
    noise_categories = {
        "ads": ["ad-", "ad_", "advertisement", "sponsor", "promotion", "banner", "google-ad", "adsense"],
        "social": ["share-", "share_", "social-", "social_", "weibo", "twitter", "facebook-share", "addtoany", "sharethis"],
        "cookie": ["cookie-", "cookie_", "consent-", "consent_", "gdpr-", "privacy-banner", "cookie-notice"],
        "comments": ["comment-list", "comment-respond", "comments"],
        "related": ["related-", "related_", "recommend-", "recommend_", "similar-", "also-read", "you-may-also", "read-more"],
        "pagination": ["pager", "pagination", "page-nav"],
        "breadcrumbs": ["breadcrumb", "breadcrumbs"],
        "sidebar": ["sidebar", "widget", "widget-area"],
        "search": ["search-", "search_", "newsletter-", "newsletter_"],
    }
    print("  Noise patterns detected before cleaning:")
    for category, patterns in noise_categories.items():
        found = []
        for el in soup1.find_all(True):
            if el.attrs is None:
                continue
            classes = " ".join(el.get("class", [])).lower()
            elem_id = (el.get("id") or "").lower()
            for p in patterns:
                if p in classes or (category == "comments" and p == elem_id):
                    found.append(f"<{el.name} class='{' '.join(el.get('class', []))}'>")
                    break
        if found:
            for f in found[:3]:
                print(f"    [{category}] {f}")
            if len(found) > 3:
                print(f"    [{category}] ... and {len(found) - 3} more")

    # Count hidden elements
    hidden_count = 0
    for el in soup1.find_all(True):
        if el.attrs is None:
            continue
        style = (el.get("style") or "").lower().replace(" ", "")
        if "display:none" in style or el.get("hidden") is not None or el.get("aria-hidden") == "true":
            hidden_count += 1
    if hidden_count:
        print(f"  Hidden elements: {hidden_count}")

    aside_count = len(soup1.find_all("aside"))
    if aside_count:
        print(f"  <aside> elements: {aside_count}")

    t0 = time.time()
    soup1 = extractor._deep_clean(soup1)
    layer1_html = str(soup1)
    layer1_time = time.time() - t0

    size_report("Layer 1", layer0_html, layer1_html)
    count_report("Layer 1", layer0_html, layer1_html)
    list_removed_elements(
        BeautifulSoup(layer0_html, "html.parser"),
        BeautifulSoup(layer1_html, "html.parser"),
        "Layer 1"
    )
    print(f"  Time: {layer1_time:.3f}s")

    # ── Layer 2: _strip_attributes ──
    separator("Layer 2: _strip_attributes (style, dimensions, interactive, URL params)")
    soup2 = BeautifulSoup(layer1_html, "html.parser")

    # Count attributes to strip
    strip_targets = {"style", "width", "height", "align", "valign", "border",
                     "cellpadding", "cellspacing", "tabindex", "draggable",
                     "contenteditable", "target", "rel"}
    attr_counts = {}
    for el in soup2.find_all(True):
        if el.attrs is None:
            continue
        for attr in el.attrs:
            if attr in strip_targets:
                attr_counts[attr] = attr_counts.get(attr, 0) + 1
    if attr_counts:
        print(f"  Attributes to strip: {attr_counts}")

    # Count URLs with tracking params
    url_params = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                  "fbclid", "ref", "source", "spm", "from"}
    tracking_urls = 0
    for el in soup2.find_all("a", href=True):
        href = el["href"]
        if any(f"{p}=" in href for p in url_params):
            tracking_urls += 1
    if tracking_urls:
        print(f"  URLs with tracking params: {tracking_urls}")

    t0 = time.time()
    soup2 = extractor._strip_attributes(soup2)
    layer2_html = str(soup2)
    layer2_time = time.time() - t0

    size_report("Layer 2", layer1_html, layer2_html)
    count_report("Layer 2", layer1_html, layer2_html)
    print(f"  Time: {layer2_time:.3f}s")

    # ── Overall compression ──
    separator("Compression Summary")
    total_reduction = (1 - len(layer2_html) / len(original_html)) * 100
    print(f"  Original HTML:    {len(original_html):>10,} chars")
    print(f"  After Layer 0:    {len(layer0_html):>10,} chars  ({(1-len(layer0_html)/len(original_html))*100:+.1f}%)")
    print(f"  After Layer 1:    {len(layer1_html):>10,} chars  ({(1-len(layer1_html)/len(original_html))*100:+.1f}%)")
    print(f"  After Layer 2:    {len(layer2_html):>10,} chars  ({(1-len(layer2_html)/len(original_html))*100:+.1f}%)")
    print(f"  Total reduction:  {total_reduction:.1f}%")

    # ── Cleaned HTML preview ──
    separator("Cleaned HTML Preview (first 6000 chars)")
    preview = layer2_html[:6000]
    print(preview)
    if len(layer2_html) > 6000:
        print(f"\n  ... ({len(layer2_html) - 6000} more chars)")

    # ── Run selector generation ──
    separator("Selector Generation")
    print("  Running generate_list_item_selectors()...")
    print("  (This calls LLM — may take 10-30s)\n")

    t0 = time.time()
    try:
        selectors = await extractor.generate_list_item_selectors(original_html)
        gen_time = time.time() - t0
        print(f"  Completed in {gen_time:.1f}s")
        print(f"  Selector groups: {len(selectors)}")
        for i, sel in enumerate(selectors):
            print(f"\n  Group {i+1}:")
            for role, value in sel.items():
                print(f"    {role:>20}: {value}")

        # ── Validate selectors on original HTML ──
        if selectors:
            separator("Validation: extract_list_items_with_selectors")
            items = extractor.extract_list_items_with_selectors(original_html, selectors)
            print(f"  Extracted {len(items)} items")
            for i, item in enumerate(items[:5]):
                print(f"\n  Item {i+1}:")
                print(f"    title: {item.get('title', '')[:80]}")
                print(f"    url:   {item.get('url', '')[:80]}")
                print(f"    summary: {item.get('summary', '')[:80]}")
            if len(items) > 5:
                print(f"\n  ... and {len(items) - 5} more items")
        else:
            print("  No selectors generated — LLM could not identify structure")

    except Exception as e:
        gen_time = time.time() - t0
        print(f"  Failed after {gen_time:.1f}s: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

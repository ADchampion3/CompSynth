import asyncio

import pytest

from comp_synth.orchestration.content_manager import ContentManager, normalize_selectors
from comp_synth.schema.content_item import WebPageItem


def test_normalize_selectors_accepts_single_dict():
    assert normalize_selectors({"item_container": "article", "url": "a"}) == [
        {"item_container": "article", "url": "a"}
    ]


def test_normalize_selectors_rejects_invalid_shape():
    with pytest.raises(ValueError, match="selectors"):
        normalize_selectors("article")


def test_javascript_source_uses_dynamic_fetch(monkeypatch):
    calls = []

    class FakeDynamicCrawler:
        async def fetch(self, source, user_selectors=None):
            calls.append((source, user_selectors))
            return [WebPageItem(url="https://example.test/a", title="A")]

        async def fetch_detail(self, item, site_name):
            return item

    class FakeTracker:
        def is_crawled(self, source, url):
            return False

        def save_articles(self, items):
            pass

    manager = ContentManager(crawl_tracker=FakeTracker())
    monkeypatch.setattr(manager, "_summarize_content", lambda title, content: ("", []))
    monkeypatch.setattr(manager, "_get_crawler", lambda source_type: FakeDynamicCrawler())
    async def fake_process_item(item, crawler, source_type, extra_metadata, semaphore, done_count, total):
        return item

    monkeypatch.setattr(manager, "_process_item", fake_process_item)

    async def run():
        return await manager._fetch_single_source(
            {
                "type": "javascript",
                "url": "https://example.test",
                "javascript": True,
                "selectors": {"item_container": "article", "url": "a"},
            }
        )

    items = asyncio.run(run())

    assert len(items[1]) == 1
    assert calls[0][0]["javascript"] is True
    assert calls[0][1] == [{"item_container": "article", "url": "a"}]

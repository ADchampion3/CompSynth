from comp_synth.schema.content_item import ContentItem


def test_content_item_default_tag_is_other():
    item = ContentItem(source="rss", url="https://example.test/a")

    assert item.tags == ["其他"]

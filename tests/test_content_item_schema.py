from comp_synth.schema.content_item import ALL_TAGS, ContentItem


def test_article_tags_are_readable_chinese_labels():
    assert ALL_TAGS == ["技术博客", "比赛信息", "就业招聘", "技术发布", "其他"]


def test_content_item_default_tag_is_other():
    item = ContentItem(source="rss", url="https://example.test/a")

    assert item.tags == ["其他"]

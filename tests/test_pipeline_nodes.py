import asyncio
from pathlib import Path

from comp_synth.orchestration.graph import route_after_deduplicate
from comp_synth.orchestration.nodes import fetch_sources, use_last_digest
from comp_synth.schema.content_item import ContentItem


def test_route_after_deduplicate_uses_new_items_not_raw_items():
    state = {"raw_items": [], "new_items": [ContentItem(source="web", url="https://x.test")]}

    assert route_after_deduplicate(state, has_last_digest=lambda: False) == "summarize"


def test_fetch_sources_missing_config_returns_actionable_error(tmp_path, monkeypatch):
    missing = tmp_path / "subscriptions.yaml"
    monkeypatch.setattr("comp_synth.config.settings.subscriptions_path", missing)

    result = asyncio.run(fetch_sources({}))

    assert result["raw_items"] == []
    assert "subscriptions.example.yaml" in result["errors"][0]


def test_fetch_sources_empty_config_skips_without_attribute_error(tmp_path, monkeypatch):
    empty = tmp_path / "subscriptions.yaml"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setattr("comp_synth.config.settings.subscriptions_path", empty)

    result = asyncio.run(fetch_sources({}))

    assert result["raw_items"] == []
    assert result["errors"] == ["No sources configured in subscriptions.yaml"]


def test_use_last_digest_returns_newest_digest(tmp_path, monkeypatch):
    older = tmp_path / "digest_20260101.md"
    newer = tmp_path / "digest_20260201.md"
    older.write_text("older", encoding="utf-8")
    newer.write_text("newer", encoding="utf-8")
    monkeypatch.setattr("comp_synth.config.settings.output_dir", tmp_path)

    result = use_last_digest({})

    assert result["report"] == "newer"
    assert result["publish_results"]["status"] == "reused"
    assert Path(result["publish_results"]["path"]) == newer

import asyncio
from pathlib import Path
from types import SimpleNamespace

from comp_synth.orchestration import nodes as nodes_module
from comp_synth.orchestration import pipeline as pipeline_module
from comp_synth.orchestration.nodes import fetch_sources, use_last_digest
from comp_synth.orchestration.pipeline import route_after_deduplicate, run_pipeline
from comp_synth.schema.content_item import ContentItem


def test_route_after_deduplicate_uses_new_items_not_raw_items():
    state = {"raw_items": [], "new_items": [ContentItem(source="web", url="https://x.test")]}

    assert route_after_deduplicate(state, has_last_digest=lambda: False) == "summarize"


def test_run_pipeline_summarizes_enriches_and_publishes_new_items(monkeypatch):
    calls = []
    item = ContentItem(source="web", url="https://x.test")

    async def fetch(state):
        calls.append("fetch_sources")
        return {"raw_items": [item]}

    async def dedup(state):
        calls.append("deduplicate")
        assert state["raw_items"] == [item]
        return {"new_items": [item]}

    async def summarize_node(state):
        calls.append("summarize")
        assert state["new_items"] == [item]
        return {"topic_groups": [{"topic": "T", "summary": "S", "articles": [], "related_historical": []}]}

    async def enrich_node(state):
        calls.append("enrich")
        assert state["topic_groups"][0]["topic"] == "T"
        return {"report": "digest"}

    async def publish_node(state):
        calls.append("publish")
        assert state["report"] == "digest"
        return {"publish_results": {"status": "success"}}

    monkeypatch.setattr(pipeline_module, "fetch_sources", fetch)
    monkeypatch.setattr(pipeline_module, "deduplicate", dedup)
    monkeypatch.setattr(pipeline_module, "summarize", summarize_node)
    monkeypatch.setattr(pipeline_module, "enrich", enrich_node)
    monkeypatch.setattr(pipeline_module, "publish", publish_node)
    monkeypatch.setattr(pipeline_module, "route_after_deduplicate", lambda state: "summarize")

    result = asyncio.run(run_pipeline())

    assert calls == ["fetch_sources", "deduplicate", "summarize", "enrich", "publish"]
    assert result["raw_items"] == [item]
    assert result["new_items"] == [item]
    assert result["report"] == "digest"
    assert result["publish_results"]["status"] == "success"


def test_run_pipeline_reuses_last_digest_when_no_new_items(monkeypatch):
    calls = []

    async def fetch(state):
        calls.append("fetch_sources")
        return {"raw_items": []}

    async def dedup(state):
        calls.append("deduplicate")
        return {"new_items": []}

    def reuse(state):
        calls.append("use_last_digest")
        return {"report": "last digest", "publish_results": {"status": "reused"}}

    async def unexpected(state):
        raise AssertionError("pipeline should stop after reusing last digest")

    monkeypatch.setattr(pipeline_module, "fetch_sources", fetch)
    monkeypatch.setattr(pipeline_module, "deduplicate", dedup)
    monkeypatch.setattr(pipeline_module, "use_last_digest", reuse)
    monkeypatch.setattr(pipeline_module, "summarize", unexpected)
    monkeypatch.setattr(pipeline_module, "publish", unexpected)
    monkeypatch.setattr(pipeline_module, "route_after_deduplicate", lambda state: "use_last_digest")

    result = asyncio.run(run_pipeline())

    assert calls == ["fetch_sources", "deduplicate", "use_last_digest"]
    assert result["report"] == "last digest"
    assert result["publish_results"]["status"] == "reused"


def test_run_pipeline_ends_when_no_new_items_and_no_digest(monkeypatch):
    calls = []

    async def fetch(state):
        calls.append("fetch_sources")
        return {"raw_items": []}

    async def dedup(state):
        calls.append("deduplicate")
        return {"new_items": []}

    async def unexpected(state):
        raise AssertionError("pipeline should stop without summarize or publish")

    monkeypatch.setattr(pipeline_module, "fetch_sources", fetch)
    monkeypatch.setattr(pipeline_module, "deduplicate", dedup)
    monkeypatch.setattr(pipeline_module, "summarize", unexpected)
    monkeypatch.setattr(pipeline_module, "publish", unexpected)
    monkeypatch.setattr(pipeline_module, "route_after_deduplicate", lambda state: "end")

    result = asyncio.run(run_pipeline())

    assert calls == ["fetch_sources", "deduplicate"]
    assert result["raw_items"] == []
    assert result["new_items"] == []
    assert result["publish_results"] == {}


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


def test_fetch_sources_returns_source_counts(tmp_path, monkeypatch):
    subscriptions = tmp_path / "subscriptions.yaml"
    subscriptions.write_text(
        """
sources:
  - type: rss
    name: Good Feed
    url: https://example.test/feed.xml
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("comp_synth.config.settings.subscriptions_path", subscriptions)

    class FakeContentManager:
        async def fetch_all(self, sources):
            return SimpleNamespace(
                items=[],
                errors=[],
                source_counts={"Good Feed": 2},
            )

    monkeypatch.setattr(nodes_module, "ContentManager", FakeContentManager)

    result = asyncio.run(fetch_sources({}))

    assert result["source_counts"] == {"Good Feed": 2}


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

import asyncio
from pathlib import Path
from types import SimpleNamespace

from comp_synth.orchestration import nodes as nodes_module
from comp_synth.orchestration import pipeline as pipeline_module
from comp_synth.orchestration.nodes import (
    _estimate_tokens,
    _fallback_report,
    _format_report,
    _format_report_grouped,
    _summarize_chunk,
    fetch_sources,
    publish,
    use_last_digest,
)
from comp_synth.orchestration.pipeline import route_after_deduplicate, run_pipeline
from comp_synth.schema.content_item import ContentItem


def test_route_after_deduplicate_uses_new_items_not_raw_items():
    state = {"raw_items": [], "new_items": [ContentItem(source="web", url="https://x.test")]}

    assert route_after_deduplicate(state, has_last_digest=lambda: False) == "summarize"


def test_run_pipeline_summarizes_and_publishes_new_items(monkeypatch):
    calls = []
    item = ContentItem(source="web", url="https://x.test")
    md_report = "## Test Topic\n### 主题概要\nTest summary\n\n### 文章列表\n1. **[title](https://x.test)** - desc"

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
        return {"report": md_report, "report_parts": [md_report]}

    async def publish_node(state):
        calls.append("publish")
        assert state["report"] == md_report
        return {"publish_results": {"status": "success"}}

    monkeypatch.setattr(pipeline_module, "fetch_sources", fetch)
    monkeypatch.setattr(pipeline_module, "deduplicate", dedup)
    monkeypatch.setattr(pipeline_module, "summarize", summarize_node)
    monkeypatch.setattr(pipeline_module, "publish", publish_node)
    monkeypatch.setattr(pipeline_module, "route_after_deduplicate", lambda state: "summarize")

    result = asyncio.run(run_pipeline())

    assert calls == ["fetch_sources", "deduplicate", "summarize", "publish"]
    assert result["raw_items"] == [item]
    assert result["new_items"] == [item]
    assert result["report"] == md_report
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


def test_fetch_sources_no_enabled_sources_returns_error(tmp_path, monkeypatch):
    monkeypatch.setattr("comp_synth.config.settings.subscriptions_path", tmp_path / "subscriptions.yaml")
    monkeypatch.setattr("comp_synth.config.settings.crawl_db_path", tmp_path / "crawl.db")

    result = asyncio.run(fetch_sources({}))

    assert result["raw_items"] == []
    assert result["errors"] == ["No enabled sources configured"]


def test_fetch_sources_returns_source_counts(tmp_path, monkeypatch):
    monkeypatch.setattr("comp_synth.config.settings.subscriptions_path", tmp_path / "subscriptions.yaml")
    monkeypatch.setattr("comp_synth.config.settings.crawl_db_path", tmp_path / "crawl.db")

    from comp_synth.schema.source import SourceConfig

    source = SourceConfig(
        source_key="Good Feed",
        source_type="rss",
        url="https://example.test/feed.xml",
        name="Good Feed",
        enabled=True,
        raw_config={"type": "rss", "name": "Good Feed", "url": "https://example.test/feed.xml"},
    )

    class FakeSourceService:
        def __init__(self, **kwargs):
            pass

        def list_sources(self):
            return [source]

    class FakeContentManager:
        async def fetch_all(self, sources, run_id=None):
            return SimpleNamespace(
                items=[],
                errors=[],
                source_counts={"Good Feed": 2},
            )

    monkeypatch.setattr(nodes_module, "SourceService", FakeSourceService)
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


# ------------------------------------------------------------------
# _summarize_chunk tests
# ------------------------------------------------------------------

def test_summarize_chunk_returns_markdown():
    md = "## AI技术\n### 主题概要\nAI summary\n\n### 文章列表\n1. **[t](u)** - s"

    class FakeLLM:
        async def ainvoke(self, messages):
            return SimpleNamespace(content=md)

    chunk = [ContentItem(source="web", url="https://x.test", title="t", summary="s")]
    result = asyncio.run(_summarize_chunk(FakeLLM(), chunk))

    assert result == md


def test_summarize_chunk_returns_none_on_empty_response():
    class FakeLLM:
        async def ainvoke(self, messages):
            return SimpleNamespace(content="")

    chunk = [ContentItem(source="web", url="https://x.test")]
    result = asyncio.run(_summarize_chunk(FakeLLM(), chunk))

    assert result is None


def test_summarize_chunk_returns_none_on_exception():
    class FakeLLM:
        async def ainvoke(self, messages):
            raise RuntimeError("LLM error")

    chunk = [ContentItem(source="web", url="https://x.test")]
    result = asyncio.run(_summarize_chunk(FakeLLM(), chunk))

    assert result is None


def test_summarize_chunk_handles_list_content():
    md = "## Topic\n### 主题概要\nSummary\n\n### 文章列表\n1. **[t](u)** - s"

    class FakeLLM:
        async def ainvoke(self, messages):
            return SimpleNamespace(content=[{"type": "text", "text": md}])

    chunk = [ContentItem(source="web", url="https://x.test", title="t", summary="s")]
    result = asyncio.run(_summarize_chunk(FakeLLM(), chunk))

    assert result == md


# ------------------------------------------------------------------
# _format_report tests
# ------------------------------------------------------------------

def test_format_report_returns_formatted_output():
    formatted = "# 主题内容报告 - 2026-05-19\n\n## 核心总览\nTest report."

    class FakeLLM:
        async def ainvoke(self, messages):
            return SimpleNamespace(content=formatted)

    raw = "## AI技术\n### 主题概要\nAI\n\n### 文章列表\n1. **[t](u)** - s"
    result = asyncio.run(_format_report(FakeLLM(), raw))

    assert result == formatted


def test_format_report_falls_back_on_error():
    class FakeLLM:
        async def ainvoke(self, messages):
            raise RuntimeError("LLM error")

    raw = "## AI技术\n### 主题概要\nAI\n\n### 文章列表\n1. **[t](u)** - s"
    result = asyncio.run(_format_report(FakeLLM(), raw))

    assert result == raw


def test_format_report_falls_back_on_empty_response():
    class FakeLLM:
        async def ainvoke(self, messages):
            return SimpleNamespace(content="")

    raw = "## AI技术\n### 主题概要\nAI"
    result = asyncio.run(_format_report(FakeLLM(), raw))

    assert result == raw


# ------------------------------------------------------------------
# _format_report_grouped tests
# ------------------------------------------------------------------

def test_format_report_grouped_single_group():
    """All chunks fit in one group → single report."""
    formatted = "# 主题内容报告\n## 核心\nOK."

    class FakeLLM:
        async def ainvoke(self, messages):
            return SimpleNamespace(content=formatted)

    chunks = ["## Topic1\nsummary1", "## Topic2\nsummary2"]
    result = asyncio.run(_format_report_grouped(FakeLLM(), chunks, max_tokens_per_group=100000))

    assert len(result) == 1
    assert result[0] == formatted


def test_format_report_grouped_splits_into_multiple_groups():
    """Chunks exceeding token limit get split into multiple groups."""
    call_count = 0

    class FakeLLM:
        async def ainvoke(self, messages):
            nonlocal call_count
            call_count += 1
            return SimpleNamespace(content=f"# Report part {call_count}")

    # Each chunk is large enough to force separate groups
    chunks = ["x" * 5000, "y" * 5000, "z" * 5000]
    result = asyncio.run(_format_report_grouped(FakeLLM(), chunks, max_tokens_per_group=1000))

    assert len(result) == 3
    assert call_count == 3


# ------------------------------------------------------------------
# _estimate_tokens tests
# ------------------------------------------------------------------

def test_estimate_tokens():
    assert _estimate_tokens("hello") == 1
    assert _estimate_tokens("a" * 150) == 50


# ------------------------------------------------------------------
# _fallback_report tests
# ------------------------------------------------------------------

def test_fallback_report_produces_valid_markdown():
    items = [
        ContentItem(source="web", url="https://a.test", title="Article A", summary="Summary A"),
        ContentItem(source="web", url="https://b.test", title="Article B", summary="Summary B"),
    ]
    report = _fallback_report(items)

    assert "## 综合" in report
    assert "### 文章列表" in report
    assert "**[Article A](https://a.test)**" in report
    assert "**[Article B](https://b.test)**" in report


def test_fallback_report_handles_empty_fields():
    items = [ContentItem(source="web", url="https://x.test")]
    report = _fallback_report(items)

    assert "**[无标题](https://x.test)**" in report
    assert "暂无摘要" in report


# ------------------------------------------------------------------
# publish tests
# ------------------------------------------------------------------

def test_publish_writes_report_to_file(tmp_path, monkeypatch):
    monkeypatch.setattr("comp_synth.config.settings.output_dir", tmp_path)
    report = "## Topic\n### 主题概要\nSummary\n\n### 文章列表\n1. **[t](u)** - s"

    result = asyncio.run(publish({"report": report, "report_parts": [report]}))

    assert result["publish_results"]["status"] == "success"
    written = Path(result["publish_results"]["path"]).read_text(encoding="utf-8")
    assert written == report


def test_publish_skips_when_no_report():
    result = asyncio.run(publish({"report": ""}))

    assert result["publish_results"]["status"] == "skipped"
    assert result["report"] == ""


def test_publish_writes_part_files_for_multiple_parts(tmp_path, monkeypatch):
    monkeypatch.setattr("comp_synth.config.settings.output_dir", tmp_path)
    part1 = "# Report Part 1"
    part2 = "# Report Part 2"
    combined = f"{part1}\n\n---\n\n{part2}"

    result = asyncio.run(publish({"report": combined, "report_parts": [part1, part2]}))

    assert result["publish_results"]["status"] == "success"
    files = result["publish_results"]["files"]
    assert len(files) == 3  # main + 2 parts
    # Main file contains combined report
    main = Path(files[0]).read_text(encoding="utf-8")
    assert main == combined
    # Part files contain individual parts
    p1 = Path(files[1]).read_text(encoding="utf-8")
    assert p1 == part1
    p2 = Path(files[2]).read_text(encoding="utf-8")
    assert p2 == part2

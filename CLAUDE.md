# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CompSynth is a content aggregation and publishing system (内容聚合与发布系统). It fetches content from RSS feeds, web pages, and Arxiv, deduplicates and persists via ChromaDB + SQLite, generates summaries via LLM, and publishes aggregated reports.

## Commands

```bash
# Install dependencies
uv sync

# Run the application
compsynth

# Run tests
pytest

# Run a single test file
pytest tests/test_crawler.py

# Run tests with verbose output
pytest -v
```

## Architecture

```
Input Sources (RSS, Web, Arxiv)
    ↓
crawlers/ — fetches and extracts structured ContentItem
    ↓
schema/ — Pydantic models (ContentItem, RSSItem, WebPageItem)
    ↓
store/ — VectorStore (ChromaDB) + CrawlTracker (SQLite) + SchemaStore (SQLite) for dedup & persistence
    ↓
orchestration/ — LangGraph pipeline: fetch → dedup → summarize → enrich → publish
    ↓
llm_provider/ — LLMRegistry supporting OpenAI-compatible and Anthropic providers
    ↓
publishers/ — publishes aggregated reports to target platforms
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `schema/content_item.py` | `ContentItem` base model with source, url, title, content, metadata |
| `crawlers/` | RSSCrawler, AdaptiveWebCrawler implementations |
| `store/vector_store.py` | ChromaDB-backed vector storage with TTL cleanup |
| `store/crawl_tracker.py` | SQLite-backed crawl tracking and deduplication |
| `store/schema_store.py` | SQLite-backed site schema storage for CSS selectors |
| `orchestration/graph.py` | LangGraph pipeline builder |
| `orchestration/nodes.py` | Pipeline nodes: fetch, dedup, summarize, enrich, publish |
| `llm_provider/registry.py` | LLM provider registry via LangChain |
| `prompt.py` | LLM prompts for analysis and report generation |

### Config

Environment variables prefixed `COMPSYNTH_` (defined in `src/comp_synth/config.py`). Key vars: `COMPSYNTH_DATA_DIR`, `COMPSYNTH_CHROMA_PERSIST_DIR`, `COMPSYNTH_CRAWL_DB_PATH`, `COMPSYNTH_SITE_SCHEMA_DB_PATH`, LLM API keys.

### Entry Point

`src/comp_synth/main.py` — async `run()` builds the LangGraph pipeline and invokes it with initial state.

### Data Flow

```
1. Load subscriptions from subscriptions.yaml
2. For each source, select appropriate crawler and fetch → list[ContentItem]
3. Deduplicate via CrawlTracker, merge today's historical content
4. Summarize: LLM groups articles by topic
5. Enrich: Search VectorStore for related content, save new items
6. Publish: LLM generates Markdown report to output/digest_YYYYMMDD.md
```

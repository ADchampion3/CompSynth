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
crawler/ — fetches and extracts structured ContentItem
    ↓
schemas/ — Pydantic models (ContentItem, RSSItem, WebPageItem, ArxivItem)
    ↓
store/ — VectorStore (ChromaDB) + CrawlTracker (SQLite) for dedup & persistence
    ↓
orchestrator/ — LangGraph pipeline: fetch_sources → deduplicate → summarize → publish
    ↓
llm/ — LLMRegistry supporting OpenAI-compatible and Anthropic providers
    ↓
publisher/ — publishes aggregated reports to target platforms
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `schemas/base.py` | `ContentItem` base model with source, url, title, content, metadata |
| `crawler/` | RSSCrawler, WebCrawler, ArxivCrawler implementations |
| `store/vector_store.py` | ChromaDB-backed vector storage with TTL cleanup |
| `store/crawl_tracker.py` | SQLite-backed crawl tracking and deduplication |
| `orchestrator/graph.py` | LangGraph pipeline builder; state flows through nodes |
| `orchestrator/nodes.py` | Pipeline nodes: fetch, dedup, summarize, publish |
| `llm/registry.py` | LLM provider registry via LangChain |

### Config

Environment variables prefixed `COMPSYNTH_` (defined in `src/comp_synth/config.py`). Key vars: `COMPSYNTH_DATA_DIR`, `COMPSYNTH_CHROMA_PERSIST_DIR`, `COMPSYNTH_CRAWL_DB_PATH`, LLM API keys.

### Entry Point

`src/comp_synth/main.py` — async `run()` builds the LangGraph pipeline and invokes it with initial state.

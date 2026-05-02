# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CompSynth is a content aggregation and publishing system (内容聚合与发布系统). It fetches content from RSS feeds, web pages, and Arxiv, deduplicates and persists via ChromaDB + SQLite, generates summaries via LLM, and publishes aggregated reports.

## Commands

```bash
# Install dependencies
uv sync

# Run the application
uv run compsynth

# Run tests
uv run python -m pytest -q

# Run a single test file
uv run python -m pytest tests/test_crawler.py

# Compile-check source and tests
uv run python -m compileall -q src tests
```

## Architecture

```
Input Sources (RSS, Web, JavaScript Web)
    ↓
crawlers/ — fetches and extracts structured ContentItem
    ↓
schema/ — Pydantic models (ContentItem, RSSItem, WebPageItem)
    ↓
store/ — VectorStore (ChromaDB) + CrawlTracker (SQLite) + SchemaStore (SQLite) for dedup & persistence
    ↓
orchestration/ — Plain async pipeline: fetch → dedup → summarize → enrich → publish
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
| `orchestration/pipeline.py` | Plain async pipeline runner and routing |
| `orchestration/nodes.py` | Pipeline nodes: fetch, dedup, summarize, enrich, publish |
| `llm_provider/registry.py` | LLM provider registry via LangChain |
| `prompt.py` | LLM prompts for analysis and report generation |

### Config

Environment variables prefixed `COMPSYNTH_` (defined in `src/comp_synth/config.py`). Key vars: `COMPSYNTH_DATA_DIR`, `COMPSYNTH_CHROMA_PERSIST_DIR`, `COMPSYNTH_CRAWL_DB_PATH`, `COMPSYNTH_SITE_SCHEMA_DB_PATH`, LLM API keys.

### Entry Point

`src/comp_synth/main.py` exposes the `compsynth` console script. Its async `run()` invokes the plain async pipeline.

### Data Flow

```
1. Load subscriptions from subscriptions.yaml
2. For each source, select appropriate crawler and fetch → list[ContentItem]
3. Deduplicate via CrawlTracker, merge today's historical content
4. Summarize: LLM groups articles by topic
5. Enrich: Search VectorStore for related content, save new items
6. Publish: LLM generates Markdown report to output/digest_YYYYMMDD.md
```

## Behavioral Guidelines

Guidelines to reduce common LLM coding mistakes. Derived from [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

Don't assume. Don't hide confusion. Surface tradeoffs.

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop and ask.

### 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

### 3. Surgical Changes

Touch only what you must. Clean up only your own mess.

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that YOUR changes made unused, but not pre-existing dead code.

Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

- "Add validation" → write tests for invalid inputs, then make them pass
- "Fix the bug" → write a test that reproduces it, then make it pass
- "Refactor X" → ensure tests pass before and after

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

## Design Context

### Users

Researchers, engineers, and technically-minded readers who track Chinese-language technical blogs and publications. They arrive to triage a day's worth of feeds, quickly separate signal from noise, and leave with a curated understanding. The tool will be shared publicly (open-source or published digests), so the interface must feel polished and credible to first-time visitors.

Primary use case: morning or end-of-day scan — open the inbox, skim topic clusters, read a few articles, check the digest. Speed matters, but so does the feeling of reading something well-edited.

### Brand Personality

**Calm, precise, editorial.** Three words: **measured, authoritative, unhurried**.

The interface should feel like a well-edited newspaper or research journal's table of contents — information-dense but not overwhelming, every element placed with intention. Not a dashboard. Not a terminal. An editor's desk.

### Aesthetic Direction

Editorial/magazine with bilingual typographic sensitivity. Type-driven, spacious, restrained. Typography and spacing do the heavy lifting — not color, not decoration. Both light and dark themes following system preference (light primary). Japanese editorial design sensibility: attention to grid, negative space, and bilingual type harmony.

Anti-references: generic SaaS dashboards, AI-generated aesthetics (glassmorphism, gradient text, cyan-on-dark), developer-tool monospace-everything.

### Design Principles

1. **Typography first.** Type hierarchy, weight, and spacing carry the visual identity. Choose fonts that honor both Latin and Chinese text equally.
2. **Restraint as style.** Every decorative element must justify itself. White space is editorial voice.
3. **Hierarchy through weight, not color.** Use size, weight, and proximity for visual priority. Color is for semantic meaning and sparing accent.
4. **Bilingual harmony.** Design the type system so English UI labels and Chinese content both feel native.
5. **Quiet authority.** No shouting. No animation to impress. Clarity and craft earn attention.

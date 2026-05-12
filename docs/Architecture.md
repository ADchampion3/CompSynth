# CompSynth Architecture

## Overview

CompSynth is a Python CLI/package for local content aggregation. The runtime path is:

```text
subscriptions.yaml
  -> orchestration.nodes.fetch_sources
  -> orchestration.content_manager.ContentManager
  -> crawlers
  -> store.CrawlTracker
  -> orchestration.nodes.summarize/publish
  -> output/digest_YYYYMMDD.md
  -> orchestration.nodes.notify
  -> publishers (email, ...)
```

## Modules

| Area | Path | Responsibility |
|---|---|---|
| CLI | `src/comp_synth/main.py` | Console entry point and pipeline invocation. |
| Config | `src/comp_synth/config.py` | Pydantic settings loaded from `COMPSYNTH_` env vars and `.env`. |
| Schemas | `src/comp_synth/schema/` | `ContentItem`, `RSSItem`, `WebPageItem`, `SourceConfig`, and site schema models. |
| Crawlers | `src/comp_synth/crawlers/` | RSS, adaptive static web, dynamic JavaScript web fetching and extraction. |
| Orchestration | `src/comp_synth/orchestration/` | Plain async pipeline, source dispatch, deduplication, enrichment. |
| Services | `src/comp_synth/services/` | Business logic: source management, article operations, crawl runs, dashboard, reports. |
| API | `src/comp_synth/api/` | FastAPI application with REST routers for articles, sources, crawls, tags, reports, dashboard. |
| LLM providers | `src/comp_synth/llm_provider/` | LangChain provider registry for OpenAI-compatible and Anthropic models. |
| Store | `src/comp_synth/store/` | SQLite article tracking, site schema cache, migrations. |
| Store repos | `src/comp_synth/store/repositories/` | Data access layer: article, source, crawl outcome, report, site schema repositories. |
| Publishers | `src/comp_synth/publishers/` | Notification publishers: email (SMTP with auto-detect, Markdown→HTML), registry for channel lookup. |
| Utilities | `src/comp_synth/utils/` | Shared utilities: logging (Loguru), JSON extraction from LLM output. |

## Pipeline

```text
fetch_sources
  -> deduplicate
  -> route_after_deduplicate
       -> summarize -> publish -> notify
       -> use_last_digest
       -> end
```

Routing after deduplication uses `new_items`, not `raw_items`, so historical items merged by `ContentManager.merge_historical_items()` still flow into summarization. When there are no new items and a prior `digest_*.md` exists, `use_last_digest` returns the newest digest with a `reused` status.

## Source Dispatch

`SourceService` manages source configuration with YAML as source of truth and DB as runtime cache:
- On app startup: YAML → DB full overwrite via `import_yaml()`.
- On API writes (create/update/delete): DB updated, then `export_yaml()` keeps YAML in sync.
- On reads: from DB; falls back to YAML if no DB is configured.

`ContentManager` routes sources by `type`:

- `rss` -> `RSSCrawler.fetch_feed()` plus detail fetch and persistence.
- `web` -> `AdaptiveWebCrawler.fetch_page()`.
- `javascript` -> `DynamicWebCrawler.fetch()` so `javascript: true` can force browser rendering.

Selectors are normalized once at the orchestration boundary. A single selector mapping is accepted for backward compatibility, and a list of selector mappings is the preferred form.

`ContentManager` also records one source crawl outcome per configured source. Web and JavaScript sources use that history as a selector health signal: when a source has multiple successful crawl days with zero new items, `AdaptiveWebCrawler` can bypass cached DB selectors and allow one stale-selector LLM refresh subject to a separate cooldown. User-provided selectors are still tried first and are not overwritten automatically.

The `SourceCrawlOutcomeRepository` computes per-source health status (healthy/stale/failed) based on recent crawl outcomes, exposed via the sources API as `crawl_status`, `last_crawled_at`, `last_new_item_count`, `recent_zero_days`, and `last_error`.

## Persistence

`CrawlTracker` stores article metadata in SQLite via `ArticleRepository`. Tags are persisted inside `extra_metadata["tags"]` on both insert and update. RSS feed URLs are stored as metadata so `get_last_crawl_time(source, feed_url)` can be feed-specific.

`SourceOutcomeStore` stores per-source crawl outcomes in SQLite. The outcome table records source key, type, site, URL, new item count, error, and crawl time so zero-result days can be distinguished from fetch errors.

`SchemaStore` stores cached CSS selectors and LLM call timestamps. It also tracks stale selector refresh attempts separately from normal selector learning, preserving the regular 24-hour LLM rate limit while allowing guarded recovery from stale cached selectors.

## Notification

The `notify` pipeline node sends the generated report to all configured channels. Channels are comma-separated in `COMPSYNTH_NOTIFICATION_CHANNELS` (env var). Currently supported: `email`.

`BasePublisher` defines the interface: `get_config()` returns publisher-specific settings from global config, `publish(report, config)` sends the report. Each publisher is registered by channel name in `publishers/registry.py`.

`EmailPublisher` converts Markdown to HTML (via `markdown` library with tables/fenced_code extensions), builds a `multipart/alternative` MIME message (text/plain + text/html), and sends via SMTP. SMTP server auto-detects from sender domain (13 providers preconfigured). Supports both STARTTLS (port 587) and implicit TLS/SSL (port 465).

## LLM Configuration

`LLMRegistry` registers configured providers at startup. If code requests an unconfigured provider, it raises an actionable error naming `COMPSYNTH_OPENAI_API_KEY`, `COMPSYNTH_ANTHROPIC_API_KEY`, and `COMPSYNTH_MODEL`.

`DOMExtractor` lazy-loads the LLM, so non-LLM selector extraction can run without API keys.

Both `nodes.py` (pipeline summarize) and `content_manager.py` (per-article summarize) use a 3-retry loop for LLM output parsing. JSON is extracted from raw LLM output via `utils/json_extraction.py`, which handles markdown code-block wrapping and mixed text. On all-retries failure, a fallback grouping or raw-text summary is used.

## Verified Commands

```bash
uv run python -m compileall -q src tests
uv run python -m pytest -q
uv run compsynth --help
```

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CompSynth is an information subscription and viewing system (信息订阅与阅读系统). It fetches content from RSS feeds, web pages, and Arxiv, deduplicates and persists via SQLite, generates summaries via LLM, and publishes aggregated reports. The system exposes a FastAPI HTTP API and a Typer CLI that share a common service layer.

## Commands

```bash
# Install dependencies
uv sync

# Run the full pipeline (crawl → dedup → summarize → publish)
uv run compsynth

# Start the API server (serves API; frontend is separate)
uv run compsynth serve [--host 127.0.0.1] [--port 8000]

# CLI subcommands
uv run compsynth crawl              # Run crawl pipeline only
uv run compsynth dashboard          # Print dashboard summary JSON
uv run compsynth status             # Human-readable system health check
uv run compsynth status --json      # Machine-readable health check
uv run compsynth doctor             # Validate setup (env, DB, API keys, SMTP)
uv run compsynth logs [--last] [-n 50] [--level ERROR]  # View log files
uv run compsynth notify [--file <path>]  # Send digest via notification channels
uv run compsynth reports list       # List generated reports
uv run compsynth reports get <id>   # Get report content
uv run compsynth sources import     # Import subscriptions.yaml → DB
uv run compsynth sources export     # Export DB → subscriptions.yaml
uv run compsynth config show        # Print effective config (secrets masked)

# Global options (apply to all commands)
uv run compsynth -v/--verbose       # Debug-level output
uv run compsynth -q/--quiet         # Suppress non-error output
uv run compsynth --cron             # Cron mode: suppress JSON summary on success
uv run compsynth --db-path <path>   # Override SQLite database path
uv run compsynth -V/--version       # Print version

# Run tests
uv run python -m pytest -q

# Run a single test file
uv run python -m pytest tests/test_crawler.py

# Compile-check source and tests
uv run python -m compileall -q src tests
```

## Architecture

```
CLI (Typer)                      FastAPI API
    │                                │
    └──────────┬─────────────────────┘
               v
        services/ — shared business logic
               │
    ┌──────────┼──────────────────┐
    v          v                  v
orchestration/  store/           llm_provider/
pipeline nodes  repositories     LLM registry
    │          + SQLAlchemy
    v
crawlers/ + publishers/
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `cli/app.py` | Typer CLI root app with all commands (crawl, serve, dashboard, status, doctor, logs, notify, reports, sources, config) |
| `cli/exit_codes.py` | Exit code constants (EXIT_SUCCESS, EXIT_PARTIAL, EXIT_FATAL) |
| `api/app.py` | FastAPI application factory with CORS, error handlers, lifespan YAML→DB sync |
| `api/deps.py` | Dependency injection: session factory, settings, DB init |
| `api/routers/` | Route handlers: articles, sources, crawls, reports, dashboard, tags, settings |
| `api/schemas.py` | Pydantic request/response models for API endpoints |
| `api/mappers.py` | Domain ↔ API response mappers |
| `services/article_service.py` | Article list, detail, filters, state mutations |
| `services/source_service.py` | Source CRUD, YAML import/export, health, test |
| `services/crawl_service.py` | Crawl orchestration: run all, run one, status tracking |
| `services/report_service.py` | Report listing, detail, generation |
| `services/dashboard_service.py` | Dashboard summary: counts, health, important unread |
| `services/settings_service.py` | Settings read/write from DB overrides |
| `schema/content_item.py` | `ContentItem` base model with source, url, title, content, metadata |
| `schema/source.py` | `SourceConfig` model for subscription source definitions |
| `schema/report.py` | Report metadata model |
| `schema/crawl_run.py` | Crawl run tracking model |
| `crawlers/` | RSSCrawler, AdaptiveWebCrawler, DynamicWebCrawler implementations |
| `crawlers/extractors.py` | `DOMExtractor` for CSS-selector and LLM-based content extraction |
| `store/models.py` | SQLAlchemy ORM models |
| `store/database.py` | Engine and session factory setup |
| `store/migrations.py` | SQLite schema bootstrap and migration tracking |
| `store/repositories/` | Data access layer: article, source, crawl_run, report, article_state, source_crawl_outcome, settings, site_schema |
| `orchestration/pipeline.py` | Plain async pipeline runner and routing |
| `orchestration/nodes.py` | Pipeline nodes: fetch, dedup, summarize, publish, notify |
| `orchestration/content_manager.py` | Source dispatch, concurrency control, detail fetch orchestration |
| `llm_provider/registry.py` | LLM provider registry via LangChain |
| `utils/json_extraction.py` | Shared JSON extraction from LLM output (code blocks, mixed text) |
| `utils/logging.py` | Loguru logger configuration |
| `utils/rate_limiter.py` | Per-domain rate limiting |
| `prompt.py` | LLM prompts for analysis and report generation |
| `publishers/base.py` | `BasePublisher` abstract class with `get_config()` and `publish()` |
| `publishers/email.py` | `EmailPublisher` — SMTP with auto-detect, Markdown→HTML, multipart/alternative |
| `publishers/registry.py` | Publisher registry — maps channel names to publisher classes |

### Config

Settings are defined in `src/comp_synth/config.py` using `pydantic-settings`. Environment variables prefixed `COMPSYNTH_` (loaded from `.env` file). Key vars: `COMPSYNTH_DATA_DIR`, `COMPSYNTH_CRAWL_DB_PATH`, `COMPSYNTH_SITE_SCHEMA_DB_PATH`, `COMPSYNTH_SUBSCRIPTIONS_PATH`, LLM API keys.

DB settings can override env vars at runtime via `apply_db_overrides()`.

**YAML/DB sync**: On startup (both CLI pipeline and API server), `subscriptions.yaml` is synced to `crawl_state.db` (YAML is source of truth for import). The API server and CLI pipeline both read from the DB at runtime.

### Entry Point

`src/comp_synth/main.py` is the backward-compat shim. The real CLI entry point is `src/comp_synth/cli/app.py` (Typer app). Console script: `compsynth`.

Subcommands:
- `compsynth` (no subcommand): runs full pipeline (crawl → dedup → summarize → publish → notify)
- `compsynth serve`: starts FastAPI server on http://127.0.0.1:8000
- `compsynth crawl`: runs crawl pipeline only
- `compsynth dashboard`: prints dashboard JSON
- `compsynth status`: human-readable system health
- `compsynth doctor`: validates setup (env, DB, keys, SMTP)
- `compsynth logs`: views log files
- `compsynth notify`: sends digest via notification channels
- `compsynth reports list/get`: report management
- `compsynth sources import/export`: subscription source sync between YAML and DB
- `compsynth config show`: prints effective configuration

### Data Flow

```
1. On startup: sync subscriptions.yaml → source DB (YAML is source of truth)
2. Load enabled sources from DB (fallback to YAML if no DB configured)
3. For each source, select appropriate crawler and fetch → list[ContentItem]
4. Deduplicate via CrawlTracker, merge today's historical content
5. Summarize: LLM groups articles by topic (3-retry with JSON extraction)
6. Publish: LLM generates Markdown report to output/digest_YYYYMMDD.md
7. Notify: send report to configured channels (email via SMTP)
```

### API Endpoints

All routes are prefixed `/api`:

| Group | Endpoints |
|-------|-----------|
| Articles | `GET /api/articles` (paginated list with filters/sort), `GET /api/articles/{id}`, `PATCH .../state`, `PATCH .../like`, `PATCH .../note`, `GET .../related` |
| Sources | `GET /api/sources`, `POST /api/sources`, `PATCH /api/sources/{key}`, `DELETE /api/sources/{key}`, `POST /api/sources/test`, `POST /api/sources/import-yaml`, `GET /api/sources/export-yaml` |
| Crawls | `POST /api/crawls` (run all), `POST /api/crawls/{key}` (run one), `GET /api/crawls/{run_id}`, `GET /api/crawls` (history) |
| Reports | `GET /api/reports`, `GET /api/reports/{id}`, `POST /api/reports/generate` |
| Dashboard | `GET /api/dashboard` |
| Tags | `GET /api/tags` |
| Settings | `GET /api/settings`, `PATCH /api/settings` |

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

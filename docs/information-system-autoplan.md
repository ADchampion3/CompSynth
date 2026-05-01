# Information Subscription System Autoplan

Generated: 2026-05-01
Branch: develop
Status: DRAFT

## Plan Summary

Expand CompSynth from a local content aggregation CLI into a full information subscription and viewing system. The first complete product should let a user manage sources, run or schedule crawls, browse an article inbox, inspect article details with LLM summaries and historical context, review generated reports, and feed user preferences back into ranking and filtering.

The plan keeps the existing crawler, deduplication, LLM summary, vector search, SQLite, ChromaDB, and Markdown digest pipeline. The new work adds a typed service layer, HTTP API, frontend, source health views, user reading states, report metadata, and a small scheduler boundary.

## Premises

1. The user does not need another generic RSS reader. The job is to reduce reading time and preserve useful context.
2. The existing pipeline is valuable and should become the backend core instead of being replaced.
3. SQLite is sufficient for the first local-first product. The plan should not introduce Postgres, accounts, or multi-tenant auth in the first release.
4. The first frontend should be an operational workbench: dense, searchable, and stateful, not a marketing-style page.
5. Feedback must be saved from day one. Without read, liked, ignored, and later-read state, the system cannot improve its filtering.
6. The API must be designed before the frontend so the CLI, scheduler, and web app reuse the same application services.

## What Already Exists

| Sub-problem | Existing code | Reuse decision |
|---|---|---|
| Source configuration | `subscriptions.yaml`, `subscriptions.example.yaml` | Keep YAML import/export; add database-backed editable sources later |
| RSS/web/JS crawling | `src/comp_synth/crawlers/` | Reuse existing crawler classes behind a source service |
| Source dispatch | `ContentManager.CRAWLER_MAP` | Keep as first strategy registry, expose through crawl service |
| Deduplication | `CrawlTracker`, `ArticleRepository.is_crawled` | Reuse article id strategy, then formalize unique source/url index |
| Article storage | `ArticleModel`, `ArticleRepository` | Extend schema with reading state, importance, and topic/report relations |
| Source health | `SourceCrawlOutcomeModel`, source outcome repository | Promote to API-visible health dashboard |
| Selector refresh | schema store + source outcome tracking | Expose stale selector warnings and manual refresh in Sources UI |
| LLM article summary | `ContentManager._summarize_content` | Keep, but move behind an article enrichment service |
| Topic grouping | `orchestration.nodes.summarize` | Reuse for report generation; persist topic groups instead of only returning runtime state |
| Historical context | `VectorStore` and `ContentManager.enrich` | Expose related historical articles in article and topic detail views |
| Digest output | `orchestration.nodes.publish`, `output/digest_YYYYMMDD.md` | Keep Markdown output; add report metadata and API listing |
| CLI entry | `src/comp_synth/main.py` | Keep CLI as a thin caller of application services |

## Product Scope

### In Scope For Version 1

1. Source management
   - List configured sources.
   - Show source type, URL, last crawl, last error, recent new item counts, selector health.
   - Import `subscriptions.yaml` into the database.
   - Export database sources back to `subscriptions.yaml` explicitly.
   - Enable, disable, archive, test, and run sources through API and frontend.
   - Defer full in-UI source creation and selector editing to V1.1 if it slows the reading loop.

2. Article inbox
   - Paginated article list.
   - Filters: source, tag, read state, liked state, ignored state, date range, text search.
   - Sorts: crawled time, published time, source, importance.
   - Actions: mark read/unread, like/unlike, ignore/unignore, later-read.

3. Article detail
   - Title, source, URL, published time, crawled time.
   - Summary, tags, content excerpt/full content when stored.
   - Related historical articles from vector search.
   - User note field.

4. Reports
   - List generated reports by date.
   - Render Markdown digest in the frontend.
   - Regenerate report for a date range and selected sources/tags.
   - Keep existing Markdown export path.

5. Crawl operations
   - Run full crawl manually.
   - Run one source manually.
   - Track running, success, partial failure, and failure states.
   - Persist per-run metadata.
   - Return a run id immediately for long operations.

6. Frontend shell
   - Dashboard, Inbox, Article Detail, Reports, Sources, Settings.
   - Responsive desktop-first layout with usable mobile read views.
   - Loading, empty, error, partial, and stale-data states.

7. Developer experience
   - `uv run compsynth serve` starts the API.
   - `npm --prefix frontend run dev` starts the frontend.
   - README updated with web app setup and common failure fixes.

### Explicitly Not In Scope For Version 1

| Deferred item | Reason |
|---|---|
| Multi-user accounts and permissions | Adds auth and tenancy complexity before the local product is proven |
| Hosted SaaS deployment | Changes data, auth, rate limit, and security assumptions |
| Browser extension | Valuable later, not needed to validate core reading workflow |
| Mobile native app | Responsive web detail view is enough for first release |
| Full email/newsletter ingestion | Different ingestion and unsubscribe rules; add after source model stabilizes |
| Collaborative annotations | Needs identity and conflict model |
| Real-time push updates | Manual refresh and polling are sufficient for local-first v1 |

## Recommended Architecture

Use a modular monolith:

```text
frontend/
  React + TypeScript + Vite
  TanStack Query for server-state fetching
  Router pages: Dashboard, Inbox, Article, Reports, Sources, Settings
        |
        v
src/comp_synth/api/
  FastAPI app, routers, response schemas
        |
        v
src/comp_synth/services/
  ArticleService, SourceService, CrawlService, ReportService, PreferenceService
        |
        v
src/comp_synth/store/
  SQLAlchemy repositories, migrations, Chroma/vector adapter
        |
        v
src/comp_synth/orchestration/
  Existing pipeline nodes and ContentManager reused by services
```

This keeps implementation simple. The API and CLI share services. The frontend does not call crawler or store code directly. Background jobs stay inside the Python process until there is a proven need for a separate worker.

## Data Model Plan

### Extend Articles

Add columns or companion table for:

| Field | Type | Purpose |
|---|---|---|
| `read_state` | string | unread, read, later, ignored |
| `liked` | int/bool | already exists, keep |
| `importance_score` | float nullable | ranking support |
| `user_note` | text | personal knowledge capture |
| `last_viewed_at` | datetime nullable | reading history |
| `source_key` | string | stable join to managed source |

Recommendation: use a companion `article_states` table instead of overloading `articles`, because article metadata and user interaction state change at different rates.

### Source Of Truth

Runtime source configuration moves to SQLite after first import. `subscriptions.yaml` remains an import/export format, not the runtime source of truth.

Import behavior:

1. Preview changes before applying: added, updated, archived, unchanged, conflict.
2. Match existing sources by stable `source_key`; fallback match by normalized URL only during first import.
3. On conflict, require explicit overwrite or keep-existing decision.
4. Never silently delete DB sources during import; mark missing YAML sources as candidates for archive.

Export behavior:

1. Export is explicit and user-triggered.
2. Export writes only active sources unless the user asks for archived sources.
3. Export preserves selector lists and source type.

### Add Sources Table

| Field | Purpose |
|---|---|
| `source_key` | stable primary key |
| `name` | display name |
| `type` | rss, web, javascript |
| `url` | source URL |
| `enabled` | disable without deleting |
| `selectors` | JSON selector list |
| `crawl_frequency` | manual, hourly, daily |
| `priority` | low, normal, high |
| `archived_at` | soft delete marker |
| `created_at`, `updated_at` | audit |

Source deletion in V1 is archive-only. Hard delete is a future maintenance command, not a normal API operation.

### Article Identity

Article state must not depend on mutable source names. New rows use:

- `source_key`: stable source identifier.
- `canonical_url`: normalized URL after redirects when available.
- `article_id`: stable hash or computed key from `source_key + canonical_url`.

Legacy rows keep their existing ids. Migration backfills `source_key` by URL/source matching and stores the legacy id as an alias where needed. State joins use `article_id`, not title, display source, or mutable URL text.

### Add Crawl Runs

Persist each manual or scheduled run:

| Field | Purpose |
|---|---|
| `run_id` | primary key |
| `scope` | all or one source |
| `status` | running, success, partial, failed |
| `started_at`, `finished_at` | timeline |
| `new_items`, `errors` | run summary |
| `error_text` | operator diagnosis |

Run status enum:

- `queued`
- `running`
- `cancel_requested`
- `success`
- `partial`
- `failed`
- `timed_out`

Every run stores heartbeat timestamps. API startup recovers stale `running` rows by marking them `timed_out` if heartbeat exceeds the configured timeout. Repeated crawl requests use idempotency keys so double-clicks do not start duplicate runs. Per-source child run rows track source-level progress and errors.

### Add Reports

Persist report metadata while keeping Markdown files:

| Field | Purpose |
|---|---|
| `report_id` | primary key |
| `title` | display title |
| `date_from`, `date_to` | covered range |
| `filters` | source/tag filters |
| `markdown_path` | existing output file |
| `created_at` | listing |

## API Plan

### API Contract Rules

Define OpenAPI/Pydantic request and response schemas before frontend component work.

Rules:

- Article list uses cursor or offset pagination from day one.
- Sort keys are enumerated: `crawled_at`, `published_at`, `importance`, `source`.
- State values are enumerated: `unread`, `read`, `later`, `ignored`.
- Errors use a consistent envelope: `problem`, `cause`, `fix`, `details`.
- Already-running crawls return `409` with the existing `run_id`.
- Dashboard supports partial failure responses instead of all-or-nothing failure.
- Frontend optimistic updates must reconcile with server responses.

### Articles

| Endpoint | Purpose |
|---|---|
| `GET /api/articles` | paginated list with filters and sorting |
| `GET /api/articles/{article_id}` | article detail |
| `PATCH /api/articles/{article_id}/state` | read, unread, later, ignored |
| `PATCH /api/articles/{article_id}/like` | like/unlike |
| `PATCH /api/articles/{article_id}/note` | save user note |
| `GET /api/articles/{article_id}/related` | historical related articles |

### Sources

| Endpoint | Purpose |
|---|---|
| `GET /api/sources` | list sources with health |
| `POST /api/sources` | create source |
| `PATCH /api/sources/{source_key}` | update source |
| `DELETE /api/sources/{source_key}` | delete or disable source |
| `POST /api/sources/test` | test source config without saving |
| `POST /api/sources/import-yaml` | load existing subscriptions |
| `GET /api/sources/export-yaml` | export current config |

### Crawl

| Endpoint | Purpose |
|---|---|
| `POST /api/crawls` | run all enabled sources |
| `POST /api/crawls/{source_key}` | run one source |
| `GET /api/crawls/{run_id}` | run status |
| `GET /api/crawls` | recent run history |

### Reports

| Endpoint | Purpose |
|---|---|
| `GET /api/reports` | report list |
| `GET /api/reports/{report_id}` | report metadata and markdown |
| `POST /api/reports/generate` | generate filtered digest |

### Dashboard

| Endpoint | Purpose |
|---|---|
| `GET /api/dashboard` | counts, source health, latest report, important topics |

## Frontend Plan

### Dashboard

First screen should answer: "What changed, what matters, and is my system healthy?"

Cards are allowed only for repeated metric blocks. The dashboard should be dense:

- New articles today.
- Unread important articles.
- Sources failing or stale.
- Latest report.
- Top tags/topics.
- Last crawl status with action button.

### Inbox

The core product surface:

- Left filter rail: source group, tags, state, date.
- Center article list: title, source, date, tags, summary, state controls.
- Right preview pane on desktop, full page on mobile.
- Keyboard path later: j/k navigation, enter open, l like, e ignore.

### Article Detail

- Header: source, time, original link, actions.
- Summary first, then content.
- Related historical articles section.
- Notes panel.
- "Why this matters" can be added after the basic state model works.

### Sources

Operational table:

- Source name, type, URL, enabled, last run, last new count, last error.
- Row actions: run now, test, edit, disable.
- Selector health warning when zero-result threshold is crossed.

### Reports

- Report list by date.
- Markdown-rendered report detail.
- Regenerate dialog with date range and filters.

### Settings

- LLM provider status.
- Data directory paths.
- Crawl concurrency and timeout.
- YAML import/export.

## Implementation Milestones

### Milestone 0: Stabilize Baseline

Goal: make the current backend safe to extend.

Tasks:

1. Fix mojibake in source strings, docs, tags, and prompts.
2. Add regression tests for tag constants and report strings.
3. Confirm `uv run python -m pytest -q` passes.
4. Document current data files and generated outputs.

Exit criteria:

- Chinese tags render correctly.
- Current CLI behavior is unchanged.
- Tests pass.

### Milestone 1: Service Layer

Goal: decouple business operations from CLI and pipeline nodes.

Tasks:

1. Add `src/comp_synth/services/article_service.py`.
2. Add `source_service.py`, `crawl_service.py`, `report_service.py`.
3. Move list/filter/state operations into services.
4. Keep `main.py` as a thin CLI wrapper.
5. Add tests with temporary SQLite paths.

Exit criteria:

- CLI still runs through the same pipeline.
- Services can list articles, get article detail, and run crawl operations in tests.

### Milestone 2: Data Model Extensions And Triage Loop

Goal: persist frontend state and prove the product can reduce reading work.

Tasks:

1. Add source, article state, crawl run, and report metadata models.
2. Add simple importance scoring based on source priority, freshness, tags, liked history, ignored state, and read state.
3. Add repository methods and tests.
4. Add `schema_migrations` table and idempotent startup migrations.
5. Back up SQLite before schema migration.
6. Preserve compatibility with existing `crawl_state.db`.
7. Define Chroma/vector mismatch behavior: article metadata remains source of truth; related results degrade gracefully when vector ids are missing.

Exit criteria:

- Existing articles remain readable.
- Article state mutations persist.
- Source health can be queried without reading logs.
- Dashboard can query important unread items.

### Milestone 3: HTTP API

Goal: expose the system through a stable API.

Tasks:

1. Add FastAPI dependency.
2. Add `src/comp_synth/api/app.py`.
3. Add routers for articles, sources, crawls, reports, dashboard.
4. Add Pydantic request/response schemas.
5. Add important unread and feedback endpoints.
6. Add `compsynth serve` CLI command.
7. Add API tests using FastAPI TestClient.

Exit criteria:

- `uv run compsynth serve` starts an API.
- Articles, sources, reports, important unread, and dashboard endpoints work against local data.
- API errors return problem, cause, and fix text.

### Milestone 4: Product Vertical Slice

Goal: prove the daily value loop with real API data.

Tasks:

1. Add `frontend/` with Vite, React, TypeScript.
2. Add TanStack Query for server-state fetching.
3. Add API client generated or typed manually from schemas.
4. Implement Dashboard with important unread, latest crawl, broken sources, latest report.
5. Implement Inbox with filters, sorting, pagination, and state mutations.
6. Implement Article Detail with summary, related fallback, and note.
7. Implement one Report detail view.
8. Add loading, empty, error, and partial states for those surfaces.

Exit criteria:

- Frontend runs locally.
- Dashboard and Inbox render real API data and feedback changes ordering.
- Build passes.

### Milestone 5: Source Health And Remaining Core UI

Goal: make source diagnosis and remaining daily workflow usable.

Tasks:

1. Implement Sources list, import YAML, export YAML, enable, disable, archive, test source, run source.
2. Implement remaining Reports list and regenerate path.
3. Implement Settings for LLM status, paths, and YAML import/export.
4. Add minimal local scheduler boundary: run on app start or daily reminder, with locking left for Milestone 7.
5. Add source conflict preview for YAML import.

Exit criteria:

- User can manage reading flow without editing files.
- User can identify broken sources and run crawls from UI.
- Reports are visible in the frontend.

### Milestone 6: Richer Feedback And Ranking

Goal: go beyond the simple triage loop.

Tasks:

1. Add "hide similar" rules or ignored-keyword rules.
2. Add saved searches or keyword watches.
3. Improve importance scoring using accumulated feedback.
4. Add topic trend and repeated-source noise controls.

Exit criteria:

- Inbox defaults to useful ordering.
- User feedback changes future ranking.

### Milestone 7: Scheduling And Packaging

Goal: make the system useful without manual runs.

Tasks:

1. Add local scheduler for enabled sources.
2. Add run locking so manual and scheduled crawls do not overlap unsafely.
3. Add docs for long-running local usage.
4. Add release checklist.

Exit criteria:

- Daily use does not require terminal commands.
- Failure recovery is visible in UI.

## CEO Review

### 0A: Premise Challenge

The key premise is that the value is not "more articles." The value is fewer, better decisions about what to read. This changes the plan: article state, source health, ranking, and reports are first-class. A plain feed reader UI would be easier but would waste the existing LLM and vector capabilities.

The second premise is local-first. This is correct for v1 because the repo already stores local SQLite, ChromaDB, and Markdown files. Hosted SaaS would force auth, tenancy, secret handling, and background worker decisions before the core loop is proven.

The third premise is that "reduce reading work" must be proven early. This changes milestone order: a thin importance score, important unread API, and feedback loop move into Milestones 2-4 rather than waiting for an advanced ranking phase.

### 0B: Existing Code Leverage Map

See "What Already Exists." The plan reuses the crawler, content manager, vector store, LLM registry, source outcome store, and digest writer. New code should wrap these pieces rather than rewrite them.

### 0C: Dream State Diagram

```text
CURRENT
  CLI reads subscriptions.yaml
  crawls sources
  deduplicates and summarizes
  writes Markdown digest

THIS PLAN
  API and frontend expose source health, inbox, article detail, reports, and feedback
  CLI and web app share services
  user state and report metadata persist

12-MONTH IDEAL
  personal/team intelligence workspace
  scheduled ingestion, semantic search, topic timelines, push digests, integrations
  multi-device sync and optional hosted mode
```

### 0C-bis: Alternatives

| Approach | Summary | Effort | Risk | Pros | Cons |
|---|---|---:|---:|---|---|
| A: Minimal API over existing SQLite | Add read-only API and simple frontend first | M | Low | Fastest visible result, low backend churn | Delays feedback loop and source editing |
| B: Service-first local workbench | Add services, state tables, API, frontend in phases | L | Medium | Best long-term base, keeps CLI and web aligned | More initial planning and tests |
| C: Full hosted SaaS | Auth, hosted database, workers, frontend, deployment | XL | High | Most ambitious commercial shape | Too much infra before local workflow proves value |

Recommendation: Approach B. It is the smallest plan that still creates the actual product.

### 0D: Scope Decisions

Approved:

- Add API and frontend.
- Add article state and source tables.
- Add source health and crawl run visibility.
- Add YAML import/export to preserve current workflow.

Deferred:

- Accounts, hosted deployment, browser extension, native mobile.

### 0E: Temporal Interrogation

Hour 1:

- User opens Dashboard and sees whether today's crawl worked.
- If source errors exist, they are visible instead of buried in logs.

Hour 6:

- User has filtered the inbox, liked useful items, ignored noise, and opened a report.
- The system has enough state to improve ordering.

Day 30:

- User expects source health, history, and report search to work reliably.
- If state is not persisted, the product feels like a demo. That is why Milestone 2 must precede heavy frontend polish.

### CEO Completion Summary

| Dimension | Verdict |
|---|---|
| Right problem | Yes: reduce reading load and preserve context |
| Scope | Correct if v1 stays local-first |
| Existing leverage | Strong: crawler, SQLite, vector, LLM, digest all reusable |
| Main risk | Adding UI before service boundaries and state model |
| Recommendation | Build service layer and state model first, then frontend |

## Design Review

UI scope detected: yes.

### Design Completeness Score

Initial score: 7/10.

Missing before implementation:

- Exact empty/error/partial states per page.
- Mobile behavior for inbox preview pane.
- Source test flow details.
- Long-title and long-URL handling.

### Information Hierarchy

Dashboard must prioritize operational truth:

1. Did the latest crawl work?
2. What is worth reading?
3. Which sources are broken?
4. What changed since the last report?

Inbox must prioritize scanning:

1. Title and source.
2. Summary and tags.
3. Time and state actions.
4. Secondary metadata only on hover/detail.

### Required UI States

| Surface | Loading | Empty | Error | Partial |
|---|---|---|---|---|
| Dashboard | skeleton metrics | no crawls yet, run first crawl | API unavailable with fix text | some widgets unavailable |
| Inbox | list skeleton | no articles match filters | query failed with retry | article list loaded, related counts pending |
| Article Detail | content skeleton | article missing | failed to load detail | related articles unavailable |
| Sources | table skeleton | no sources, import YAML | source query failed | health missing for some sources |
| Reports | list skeleton | no reports, generate one | markdown read failed | report metadata loaded, markdown missing |

### Layout Decisions

- Desktop: persistent left navigation, dense content area.
- Inbox desktop: filter rail + list + preview/detail panel.
- Mobile: navigation drawer, article list first, detail as full route.
- Cards only for repeated metrics or repeated list items.
- No landing page; app opens directly to Dashboard.

### Design Completion Summary

| Dimension | Score | Action |
|---|---:|---|
| Information hierarchy | 8 | Keep dashboard operational and inbox scan-first |
| Interaction states | 7 | Add page-specific states before frontend build |
| Responsive behavior | 7 | Define preview-to-route mobile behavior |
| Accessibility | 7 | Keyboard nav and focus states required for actions |
| Content specificity | 8 | Use real source/article/report language |
| Visual restraint | 8 | Dense workbench, not marketing UI |
| Implementation readiness | 7 | Needs endpoint contracts before component work |

## Engineering Review

### Architecture Graph

```text
CLI
  |
  v
Service Layer <-------------------- Frontend API routers
  |                                      ^
  v                                      |
ContentManager / Pipeline Nodes          |
  |                                      |
  v                                      |
Crawlers + LLM Registry + VectorStore + SQLAlchemy repositories
```

### Coupling Assessment

Current orchestration functions mix file loading, crawling, LLM calls, persistence, and report writing. The API should not call `nodes.fetch_sources` directly for interactive operations. Add service methods that can call existing components with explicit inputs and return typed results.

### Code Quality Findings

| Finding | Severity | Decision |
|---|---|---|
| Mojibake in source strings and docs | High | Fix in Milestone 0 before expanding user-facing UI |
| `ArticleRepository._to_domain` passes `id` into `ContentItem` even though id is computed | Medium | Test and fix before API serialization depends on it |
| Existing liked field is too narrow for full reading workflow | Medium | Add companion article state table |
| Reports are file-only | Medium | Add report metadata table, keep Markdown path |
| Source configuration is file-only | Medium | Add managed sources table with YAML import/export |

### Performance Review

Risks:

- Article list can become slow without indexes on `crawled_at`, `published_at`, `source`, and state fields.
- Full-text search over SQLite needs either FTS5 or a simple title/summary filter first.
- Related-article lookup should be lazy on article detail, not loaded for every inbox row.
- Running crawls through the API must not block request threads indefinitely.

Decisions:

- Add pagination from the first article endpoint.
- Add indexes with state/source/date fields.
- Keep related article calls separate.
- Return a crawl run id immediately for long operations.

### Security Review

New attack surfaces:

- Source URL input can trigger SSRF-like local network fetches if this becomes hosted.
- CSS selectors and JavaScript crawling can cause slow or malicious pages.
- Markdown report rendering can introduce unsafe HTML if not sanitized.

V1 local-first decisions:

- Validate URL scheme as http/https.
- Add crawl timeout and concurrency limits to API operations.
- Render Markdown safely in frontend.
- Document local-only trust assumptions.

### Test Diagram

| Flow/codepath | Test type | Required coverage |
|---|---|---|
| Article list filters | Repository + API tests | source, tag, state, date, pagination |
| Article state mutation | Repository + API tests | read, unread, later, ignored, like |
| Article detail | API tests | found, missing, content present/empty |
| Related articles | Service tests | vector unavailable, no matches, matches |
| Source import/export | Service tests | YAML compatibility, invalid source |
| Source test | Service/API tests | RSS, web selectors, failure |
| Crawl run | Service/API tests | success, partial failure, already running |
| Report listing | Service/API tests | markdown exists, missing file |
| Frontend dashboard | Component/e2e | loading, empty, partial, error |
| Frontend inbox | Component/e2e | filters, actions, pagination |

### Engineering Completion Summary

| Dimension | Verdict |
|---|---|
| Architecture | Sound if service layer lands before API/frontend |
| Tests | Must expand around repositories, services, API, and frontend state |
| Performance | Manageable with pagination, indexes, lazy related lookups |
| Security | Acceptable for local-first with URL validation and safe Markdown |
| Deployment | Local dev only in v1; hosted mode deferred |

## DX Review

DX scope detected: yes.

### Developer Journey Map

| Stage | Current | Target |
|---|---|---|
| Discover | README explains CLI | README explains CLI + web app |
| Install | `uv sync` | `uv sync` plus frontend install |
| Configure | edit YAML and env vars | same, plus UI import/export |
| First run | `uv run compsynth` | `uv run compsynth`, then `uv run compsynth serve` |
| Inspect output | open Markdown file | open frontend dashboard |
| Debug source | read logs | source health table and test source action |
| Extend source | edit YAML selectors | UI editor plus YAML export |
| Test | pytest only | pytest + frontend build |
| Recover | manual file inspection | run history and actionable errors |

### TTHW

Current time to useful output: about 10-20 minutes depending on LLM credentials and source setup.

Target:

- CLI hello world under 5 minutes with example source.
- Web app hello world under 10 minutes including frontend install.

### DX Scorecard

| Dimension | Score | Required improvement |
|---|---:|---|
| Getting started | 6 | Add web app commands and example data |
| API ergonomics | 7 | Keep REST nouns simple and typed |
| Error messages | 5 | Add problem/cause/fix format |
| Docs | 6 | Add web app setup and troubleshooting |
| Configuration | 7 | Preserve YAML and add UI import/export |
| Testing | 7 | Add API/frontend commands |
| Debuggability | 8 | Source health and run history improve this |
| Upgrade path | 5 | Add migration notes when DB schema changes |

## Failure Modes Registry

| Failure mode | User-visible impact | Prevention |
|---|---|---|
| Mojibake leaks into UI | Broken Chinese labels and tags | Fix encoding before frontend |
| API duplicates pipeline logic | CLI and web behavior diverge | Shared services |
| Crawl request blocks too long | UI hangs on run action | Crawl run ids and status polling |
| Source config splits between YAML and DB | User changes disappear or conflict | Explicit import/export and source of truth docs |
| Markdown renders unsafe HTML | Possible script injection in local browser | Safe renderer and sanitization |
| Article list loads all rows | Slow inbox | Pagination and indexes |
| Related articles load in list | Slow dashboard/inbox | Lazy detail endpoint |
| Frontend starts before API contract | Rework | Define schemas first |

## Error And Rescue Registry

| Error | Detection | User-facing rescue |
|---|---|---|
| Missing LLM key | settings validation/API status | "Set COMPSYNTH_OPENAI_API_KEY or COMPSYNTH_ANTHROPIC_API_KEY" |
| Missing subscriptions | source service startup | "Import YAML or create your first source" |
| Source crawl fails | crawl run error | show source, cause, retry action |
| Selector stale | zero-result health threshold | show refresh/test selector action |
| Vector store unavailable | related endpoint error | show article without related context |
| Report file missing | report detail read | show metadata and regenerate action |

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Use service-first local workbench | Mechanical | Completeness | It creates the real product while preserving existing backend | Read-only API first, hosted SaaS |
| 2 | CEO | Defer hosted SaaS and accounts | Mechanical | Pragmatic | Auth and tenancy are outside local-first v1 blast radius | Multi-user v1 |
| 3 | Design | Use dense operational dashboard | Mechanical | Explicit over clever | The product is a workbench, not a landing page | Marketing-style hero UI |
| 4 | Eng | Add companion article state table | Mechanical | DRY | Keeps user state separate from crawled article metadata | Overload ArticleModel further |
| 5 | Eng | Return crawl run id for long operations | Mechanical | Completeness | Prevents blocked requests and enables status UI | Synchronous API crawl response only |
| 6 | DX | Preserve YAML import/export | Mechanical | Bias toward action | Existing users keep current workflow while UI matures | Force DB-only config immediately |
| 7 | CEO | Pull simple triage into Milestone 2-4 | Mechanical | Completeness | Proves the core promise before broad UI polish | Delay ranking to Milestone 6 |
| 8 | Eng | Make DB runtime source of truth after import | Mechanical | Explicit over clever | Prevents silent YAML/DB drift | Dual runtime sources |
| 9 | Eng | Use archive-only source deletion in V1 | Mechanical | Completeness | Keeps historical joins and reports intact | Hard delete through normal API |
| 10 | Eng | Add schema migrations and backups | Mechanical | Completeness | Protects existing local data during expansion | Ad hoc table creation only |

## Cross-Phase Themes

1. The biggest risk is building frontend screens before service boundaries and data state are stable.
2. The second risk is treating reports as the whole product. The daily-use surface is the inbox plus source health.
3. The third risk is proving triage value too late. Important unread and feedback-driven ordering must appear in the first vertical slice.
4. Encoding quality is a release blocker because the UI will expose current mojibake directly.
5. Local-first is the right v1 constraint. Hosted mode should be a later architecture review.

## Implementation Order

1. Milestone 0: encoding and baseline tests.
2. Milestone 1: service layer.
3. Milestone 2: state/source/run/report metadata plus simple importance scoring.
4. Milestone 3: API, including important unread and feedback endpoints.
5. Milestone 4: vertical slice Dashboard, Inbox, Article Detail, one Report view.
6. Milestone 5: source health and remaining core UI.
7. Milestone 6: richer ranking and feedback.
8. Milestone 7: scheduler and packaging.

## Definition Of Done For Version 1

- A user can add or import sources without editing code.
- A user can run crawls and see failures from the UI.
- A user can browse, filter, read, like, ignore, and note articles.
- A user can open generated reports from the UI.
- Existing CLI still works.
- Core backend tests, API tests, and frontend build pass.
- README documents setup, run, test, and common failures.

<!-- /autoplan restore point: new plan file created on branch plan-selector-zero-refresh -->

# Selector Zero-Content Refresh Plan

Captured: 2026-04-30 | Branch: plan-selector-zero-refresh | Base: develop

## Plan Summary

Add a guarded selector refresh path for web and JavaScript sources when one configured source produces `0` new persisted items for multiple crawl days. The system should treat repeated zero-new-content results as a possible stale selector signal, then allow the crawler to ask the LLM for fresh selectors once instead of staying pinned to a bad cached selector.

This is a plan only. No runtime code is changed in this branch yet.

## Premises

| Premise | Assessment | Plan Response |
|---|---|---|
| A healthy source should not report `0` new items for many crawl days when the source is active. | Reasonable, but not always true. Some sources publish rarely. | Make the threshold configurable and only trigger after multiple distinct crawl dates. |
| Cached selectors can go stale silently when a site changes markup. | Valid. `AdaptiveWebCrawler._extract_list_items()` currently falls through only when selector extraction fails during the current crawl. | Persist source-level zero-count history so stale selector recovery can use historical outcomes. |
| LLM selector generation must stay rate-limited. | Valid. `SchemaStore.can_use_llm()` currently enforces a 24h per-site limit. | Add an explicit stale-selector override path with its own cooldown and audit metadata. |
| User-provided selectors should not be overwritten automatically. | Valid. They may encode a deliberate source-specific choice. | Use zero-content detection to warn/log for user selectors; auto-regenerate only cached selectors unless explicitly configured later. |

## What Already Exists

| Sub-problem | Existing Code | Reuse |
|---|---|---|
| Source dispatch and per-source result counts | `src/comp_synth/orchestration/content_manager.py` `FetchResult.source_counts` and `_fetch_single_source()` | Record counts after each source finishes. |
| Web list extraction pipeline | `src/comp_synth/crawlers/adaptive_web_crawler.py` `_extract_list_items()` | Insert health-aware selector refresh before DB selector reuse or before LLM fallback. |
| JavaScript-rendered source support | `src/comp_synth/crawlers/dynamic_web_crawler.py` delegates to `AdaptiveWebCrawler` | Benefit automatically when delegate passes source identity. |
| Cached selector persistence | `src/comp_synth/store/schema_store.py`, `site_schema_repository.py`, `models.py` | Extend repository/store with health metadata or add a dedicated source outcome table. |
| Test structure | `tests/test_crawler.py`, `tests/test_content_manager_dispatch.py`, `tests/test_store_repository.py` | Add focused repository, manager, and crawler tests. |

## Not In Scope

| Item | Rationale |
|---|---|
| RSS selector refresh | RSS does not use CSS selectors in this codepath. Zero RSS counts may indicate feed publishing cadence or feed outage, not stale selectors. |
| Automatic edits to `subscriptions.yaml` | Runtime state should not mutate user config files. Selector cache belongs in SQLite. |
| Full crawl observability dashboard | Useful later, but this feature only needs durable outcome records and actionable logs. |
| Fetching live sites during tests | Tests should be deterministic and use mocked crawler/store/LLM behavior. |

## Proposed Design

### 1. Add Per-Source Crawl Outcome Persistence

Add a new ORM model, domain shape, repository methods, and store wrapper for per-run source results.

Recommended table: `source_crawl_outcomes`

| Column | Type | Notes |
|---|---|---|
| `id` | integer primary key | Internal row id. |
| `source_key` | string indexed | Stable key: source `name` if present, else source `url`. |
| `source_type` | string | `web`, `javascript`, `rss`, etc. |
| `site_name` | string indexed | Hostname from source URL for selector lookup. |
| `source_url` | string | Original source URL. |
| `new_item_count` | integer | Number of items persisted/returned after dedup and processing. |
| `error` | text nullable | Crawl error, if any. Errors should not count as selector-zero days. |
| `crawled_at` | datetime | When this source finished. |

Store API:

```python
record_source_outcome(source: dict, count: int, error: str | None) -> None
count_recent_zero_days(source_key: str, *, days: int) -> int
last_success_count(source_key: str) -> int | None
```

Decision: use a dedicated table instead of overloading `ArticleModel`. Principle: explicit over clever. Article rows only exist when content is saved, so they cannot represent zero-result days.

### 2. Record Outcomes in ContentManager

In `ContentManager.fetch_all()`, after `_fetch_single_source()` returns, record one outcome per source. Use `source_name` as the result key for compatibility, but persist a stable `source_key` derived from `source.get("name") or source["url"]`.

Rules:

| Case | Record? | Counts Toward Stale Selector? |
|---|---:|---:|
| Success with `count > 0` | Yes | No, resets the signal naturally. |
| Success with `count == 0` | Yes | Yes, if source type is `web` or `javascript`. |
| Fetch error | Yes | No. It is an outage/fetch problem, not selector evidence. |
| Unknown source type | Yes | No. |

### 3. Add Selector Health Decision

Add config:

```python
selector_zero_refresh_days: int = 3
selector_zero_refresh_lookback_days: int = 7
selector_zero_refresh_cooldown_hours: int = 24
selector_zero_refresh_enabled: bool = True
```

For `web`/`javascript` sources, before trusting DB cached selectors, ask the store whether the source has `>= selector_zero_refresh_days` zero-result crawl dates in the lookback window and no current fetch error. If true:

1. Log a warning naming `source_key`, `site_name`, zero-day count, and threshold.
2. Skip cached DB selectors for this extraction attempt.
3. Allow LLM selector generation even if regular `can_use_llm()` says no, but only if stale-refresh cooldown allows it.
4. Save new selectors only if extracting with them yields valid data.
5. Mark the stale-refresh attempt timestamp whether the LLM succeeds or fails.

Stale refresh should not overwrite user-provided selectors by default. If user selectors produce zero items over multiple days, log that the source config likely needs manual review.

### 4. Extend SchemaStore for Refresh Metadata

Use `SiteSchemaModel` for selector-level metadata because the cooldown belongs to the cached selector for a site.

Add nullable columns:

| Column | Purpose |
|---|---|
| `last_stale_refresh_call` | Cooldown separate from regular LLM selector learning. |
| `stale_refresh_count` | Operational audit and future safety limits. |

Store methods:

```python
can_refresh_stale_selectors(site_name: str) -> bool
mark_stale_refresh_called(site_name: str) -> None
```

Keep `can_use_llm()` unchanged for normal first-time selector learning. This avoids weakening the existing 24h rate limit for ordinary extraction misses.

### 5. Thread Source Context Into Crawlers

`AdaptiveWebCrawler.fetch_page()` currently receives URL and optional user selectors, but not source identity. To check source outcome history, it needs a stable key.

Preferred change:

```python
async def fetch_page(
    self,
    url: str,
    user_selectors: list[dict[str, str]] | None = None,
    source_key: str | None = None,
) -> list[WebPageItem]:
```

Then pass it through `_crawl_list_page()` and `_extract_list_items()`. `ContentManager._fetch_web_source()` and `DynamicWebCrawler.fetch()` should pass `source.get("name") or source["url"]`.

Backward compatibility: default `source_key=None` preserves direct crawler tests and callers.

## Error & Rescue Registry

| Failure | User Impact | Rescue |
|---|---|---|
| Rarely updated source triggers unnecessary refresh | Extra LLM call and selector churn | Multi-day threshold, lookback window, and cooldown. |
| Site outage returns 0-like result | Bad selector overwrite | Errors are recorded separately and do not count as stale-selector days. |
| LLM returns poor selectors | Continued 0 results | Save only if selector extraction yields valid title + URL data. |
| User selectors are stale | Source still yields 0 | Log manual-review warning; do not overwrite user config silently. |
| JavaScript source hides content until render | Static fetch may create false zero | Dynamic crawler already delegates rendered HTML into the same adaptive extraction path. |

## Architecture

```text
subscriptions.yaml
      |
      v
ContentManager.fetch_all
      |
      +--> _fetch_single_source(source)
      |         |
      |         +--> AdaptiveWebCrawler / DynamicWebCrawler
      |                  |
      |                  +--> _extract_list_items(html, source_key)
      |                           |
      |                           +--> user selectors
      |                           +--> selector health check
      |                           +--> DB selectors or stale-refresh LLM
      |                           +--> heuristic fallback
      |
      +--> SourceOutcomeStore.record_source_outcome(...)

SchemaStore
      |
      +--> cached selectors
      +--> regular LLM rate limit
      +--> stale-refresh cooldown metadata
```

## Test Plan

Write test artifact target when implementing: `tests/test_selector_zero_refresh.py`.

| Codepath | Test |
|---|---|
| Outcome persistence records zero and non-zero source counts | In-memory SQLite repository test records rows and counts distinct zero crawl dates. |
| Errors do not count as selector-zero days | Repository test with `error="timeout"` and count 0 returns zero stale days. |
| ContentManager records one outcome per source | Fake crawlers return counts; assert store receives source key, site, type, count, error. |
| DB selectors used when zero-day threshold not met | Mock schema/outcome store and DOMExtractor; assert no stale refresh call. |
| DB selectors skipped when threshold met | Cached selector extracts invalid data; stale refresh allowed; LLM selector path called. |
| User selectors are not overwritten | User selector stale condition logs/manual warning and does not call DB selector update. |
| LLM selectors saved only after valid extraction | Generated selectors returning invalid items do not update `selectors`. |
| Dynamic crawler passes source key to delegate | Existing dynamic crawler dispatch test extended to assert source context is forwarded. |

Recommended verification:

```powershell
uv run python -m pytest -q tests/test_store_repository.py tests/test_content_manager_dispatch.py tests/test_crawler.py
uv run python -m pytest -q tests/test_selector_zero_refresh.py
```

## Implementation Steps

1. Add configuration defaults in `src/comp_synth/config.py`.
2. Add `SourceCrawlOutcomeModel` in `src/comp_synth/store/models.py`.
3. Add a repository and store wrapper for source outcome writes and zero-day queries.
4. Extend `SiteSchemaModel`, `SiteSchema`, `SiteSchemaRepository`, and `SchemaStore` for stale-refresh cooldown metadata.
5. Update `ContentManager.fetch_all()` to record per-source outcomes after each result.
6. Thread `source_key` through `ContentManager`, `AdaptiveWebCrawler`, and `DynamicWebCrawler`.
7. Add the selector health decision in `_extract_list_items()`.
8. Add deterministic tests listed above.
9. Update `docs/Architecture.md` and README selector notes after implementation.

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Persist source outcomes instead of inferring from articles | Mechanical | Explicit over clever | Zero-result days have no article rows, so a dedicated table is the correct source of truth. | Querying `ArticleModel` gaps |
| 2 | CEO | Limit auto-refresh to cached DB selectors by default | Mechanical | Completeness | Protects user-authored selectors from silent mutation while still fixing learned selectors. | Overwrite user selectors |
| 3 | Eng | Add separate stale-refresh cooldown | Mechanical | Pragmatic | Keeps normal LLM rate limiting intact and allows audited recovery for stale selectors. | Reusing `last_llm_call` only |
| 4 | Eng | Record errors but exclude them from stale-selector counts | Mechanical | Explicit over clever | Network/fetch failures should not be interpreted as selector breakage. | Treat all zero counts alike |
| 5 | DX | Add config knobs with safe defaults | Mechanical | Bias toward action | Users can tune rare publishing sources without code changes. | Hard-coded thresholds |

## CEO Review

### 0A Premise Challenge

The central risk is conflating "no new content" with "broken selector". The plan avoids that by requiring multiple successful crawl days with zero results, excluding errors, and keeping thresholds configurable. The second risk is silently changing a user-controlled selector; the plan rejects that and confines automatic regeneration to cached selectors.

### 0B Existing Code Leverage Map

The plan reuses ContentManager's existing source count aggregation, AdaptiveWebCrawler's selector fallback ladder, SchemaStore's LLM rate-limit concept, and current SQLite/SQLAlchemy repository patterns. No new crawler family, scheduler, or external service is needed.

### 0C Dream State Delta

```text
CURRENT
  Cached selectors can fail silently across runs.

THIS PLAN
  Repeated zero-result days become a stored health signal.
  Stale cached selectors can be regenerated with guardrails.

12-MONTH IDEAL
  Source health history powers alerts, dashboards, and per-source policy.
```

### 0C-bis Alternatives

| Approach | Effort | Risk | Verdict |
|---|---:|---|---|
| Dedicated source outcome table + stale-refresh selector path | Medium | Requires small schema expansion | Recommended. Clear state and testable behavior. |
| Infer from absence of articles | Low | Cannot distinguish not-run, errors, and zero results | Reject. Incorrect model. |
| Always regenerate when current extraction returns 0 | Low | LLM churn and false positives | Reject. Too noisy for rare publishers. |

### CEO Completion Summary

Strategic fit is sound: this fixes a real silent-failure mode in the crawler without widening scope into monitoring or dashboards. The plan should proceed as a targeted reliability feature with explicit state and conservative refresh rules.

## Design Review

Phase 2 skipped: no UI scope detected. The user-facing surface is configuration, logs, and documentation.

## Engineering Review

### Scope Challenge

The smallest correct implementation crosses four areas: config, store models/repositories, ContentManager outcome recording, and crawler selector decision logic. That is acceptable because all four are directly in the blast radius. A crawler-only fix would be incomplete because the trigger is multi-day history.

### Architecture Assessment

Coupling remains acceptable if the crawler depends on a small outcome query API rather than reading ContentManager state. The main code smell to avoid is passing full source dicts deep into the crawler; pass a stable `source_key` instead.

### Code Quality Assessment

Keep naming literal: `source_key`, `new_item_count`, `count_recent_zero_days`, `can_refresh_stale_selectors`. Avoid a generic "health manager" abstraction until there is more than one health policy.

### Test Coverage Assessment

The highest-risk tests are persistence semantics and the branch that skips cached selectors only when threshold and cooldown both pass. Do not rely on live network tests. Mock DOMExtractor and stores so failures identify decision logic, not site changes.

### Performance Assessment

The additional work is one insert per source per run and one bounded query per web/javascript source. With current source counts this is negligible. Add an index on `(source_key, crawled_at)` to keep lookback queries cheap.

### Eng Completion Summary

Proceed with the dedicated outcome table and narrow crawler integration. This is a medium-size, low-risk change if tests lock down error exclusion, user selector protection, and cooldown behavior.

## DX Review

Developer-facing scope detected because this changes configuration and operational behavior.

### Developer Journey

| Stage | Expected Experience |
|---|---|
| Configure sources | Existing `subscriptions.yaml` remains unchanged. |
| Run pipeline | Counts are recorded automatically. |
| Observe repeated zero results | Logs explain threshold, source key, and whether refresh was attempted. |
| Tune behavior | Environment variables adjust threshold/lookback/cooldown. |
| Debug selectors | SQLite state and logs show last LLM and stale-refresh attempts. |

### DX Scorecard

| Dimension | Score | Notes |
|---|---:|---|
| Time to use | 9/10 | Works automatically after implementation. |
| Configuration clarity | 8/10 | Needs README examples for rare publishers. |
| Error messages/logs | 8/10 | Plan requires source key, threshold, and action in logs. |
| Testability | 9/10 | Deterministic store and crawler tests are straightforward. |
| Upgrade safety | 8/10 | SQLAlchemy creates tables, but nullable columns need compatibility tests. |

### DX Implementation Checklist

| Item | Required |
|---|---|
| Document new `COMPSYNTH_SELECTOR_ZERO_REFRESH_*` env vars | Yes |
| Log when stale refresh is skipped due to cooldown | Yes |
| Log when user selectors look stale but are not auto-overwritten | Yes |
| Keep default behavior safe for rare sources | Yes |

## Cross-Phase Themes

| Theme | Phases | Resolution |
|---|---|---|
| Avoid false positives | CEO, Eng, DX | Multi-day threshold, error exclusion, cooldown. |
| Preserve user control | CEO, Eng | Do not overwrite user selectors by default. |
| Keep implementation explicit | Eng, DX | Dedicated table and literal method names. |

## Final Approval Gate

### Decisions Made

5 total, all auto-decided, 0 taste choices, 0 user challenges.

### Review Scores

| Phase | Result |
|---|---|
| CEO | Approved targeted reliability scope. |
| Design | Skipped, no UI scope. |
| Eng | Approved with required tests and explicit state model. |
| DX | Approved with config/docs/logging requirements. |

### Recommendation

Approve this plan as-is and implement on top of this branch. The highest-value implementation detail is the dedicated source outcome table; skipping it would make the multi-day trigger ambiguous and hard to test.

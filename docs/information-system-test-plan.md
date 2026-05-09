# Information Subscription System Test Plan

Generated: 2026-05-01
Branch: develop
Status: DRAFT

## Test Strategy

The expansion should be tested in layers: repositories first, services second, API third, frontend last. The existing crawler tests should remain focused on extraction behavior. New web app tests should not depend on live external sites.

## Backend Unit Tests

| Area | Required tests |
|---|---|
| Article state repository | create state, update state, like/unlike, note update, missing article |
| Source repository | create/update/disable/delete, selector JSON round trip, YAML import/export |
| Crawl run repository | running/success/partial/failed states, counts, errors |
| Report repository | metadata save/list/detail, missing markdown path |
| Article service | filters, pagination, sorting, detail, related fallback |
| Importance scoring | score changes after like/ignore/read/later, stable ordering, ignored noise drops from top priority |
| Source service | health merge with `SourceCrawlOutcomeModel`, stale selector status |
| Crawl service | run all, run one, concurrent run lock |
| Report service | list reports, read markdown, generate filtered report |
| Schema migrations | legacy DB migration, repeated startup migration, malformed old data, backup creation |
| Source import/export | conflict preview, overwrite, keep existing, archive candidate, source key collision |

## API Tests

Use FastAPI TestClient with temporary SQLite and temporary output directories.

| Endpoint group | Required cases |
|---|---|
| Articles | list empty, list filtered, detail found/missing, state mutation, like mutation, note mutation |
| Sources | list empty, import YAML, export YAML, create invalid URL, test source failure |
| Crawls | create run, get status, partial failure, already-running behavior |
| Reports | list empty, detail with markdown, detail missing markdown, generate request validation |
| Dashboard | no data, healthy data, partial source failures |
| Ranking | important unread populated, ignored item removed from important list, feedback mutation updates dashboard |

## Frontend Tests

| Surface | Required cases |
|---|---|
| Dashboard | loading, empty, source failure, latest report present |
| Inbox | filter changes query params, state buttons update list, empty filtered state |
| Article detail | article found, related unavailable, note save error |
| Sources | run source button, test source failure, stale selector warning |
| Reports | report list, markdown detail, missing markdown error |

## Browser Workflow Tests

Add one Playwright path with mocked API or the test API:

1. Open Dashboard.
2. Confirm important unread items render.
3. Go to Inbox.
4. Apply a tag/source filter.
5. Open an article.
6. Mark it liked and later-read.
7. Save a note.
8. Return to Dashboard and confirm ordering/state changed.
9. Open Sources and run/test one source.
10. Open Reports and render one Markdown report.

## Integration Tests

1. Seed two sources and five articles.
2. Start API test app.
3. Load dashboard data.
4. List inbox with filters.
5. Mark one article liked and later-read.
6. Open detail and related endpoint.
7. Generate report metadata pointing to a temp Markdown file.
8. Read report through API.
9. Apply like/ignore/later feedback and confirm important unread ordering changes.

## Migration And Compatibility Tests

1. Create a fixture copy of a pre-expansion `crawl_state.db`.
2. Run startup migrations once.
3. Run startup migrations a second time and confirm idempotency.
4. Confirm existing articles are readable.
5. Confirm article state backfills without changing article content.
6. Confirm article detail works correctly when no related articles are available.
7. Confirm CLI digest generation still works through the service path.

## Manual QA Checklist

- `uv run python -m pytest -q` passes.
- `uv run compsynth` still writes a digest.
- `uv run compsynth serve` starts API.
- Frontend dev server loads Dashboard.
- Frontend production build passes.
- A broken source shows a visible error in Sources.
- A zero-result source can be distinguished from a fetch error.
- A YAML import conflict is previewed before applying.
- A repeated crawl click returns the existing run instead of starting a duplicate.
- Long article titles and URLs do not break layout.
- Markdown report content cannot execute unsafe HTML.

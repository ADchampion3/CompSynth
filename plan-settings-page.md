<!-- /autoplan restore point: /c/Users/24277/.gstack/projects/ADchampion3-CompSynth/develop-autoplan-restore-20260503-162250.md -->

# Plan: Frontend Settings Page with Backend Config Sync

## Summary

Add a Settings page to the CompSynth frontend where users can view and modify backend configuration (API URL, LLM settings, crawler params, etc.). Changes are persisted to a SQLite `settings` table via a new `/api/settings` endpoint. The backend reads config from the DB at startup (with `.env` as fallback), and the frontend stores its own API base URL in `localStorage`.

## Premises

1. **Frontend API URL is a client-side concern.** The backend URL the frontend connects to is stored in `localStorage`, not synced via API. This is the Vite dev server proxy target or production API host.
2. **Server-side config is a backend concern.** LLM keys, model names, crawler params, storage paths — all live in the backend `Settings` model and are managed via a new REST API.
3. **`.env` file is the initial seed, not the source of truth at runtime.** After first startup, the `settings` DB table overrides `.env` values. Writing directly to `.env` at runtime is fragile (concurrent writes, permission issues, Docker read-only mounts).
4. **Sensitive values (API keys) are masked in API responses.** The settings endpoint returns `***masked***` for any field containing "key" or "secret". Writes accept the masked value as a no-op.
5. **Changes to some settings require a restart to take effect.** The API returns a `requires_restart` flag per setting. The UI shows a banner when restart-pending settings are changed.

## Architecture

### Backend Changes

#### 1. Settings Repository (`store/repositories/settings_repository.py`)

New file. A SQLite-backed key-value store for config overrides.

```python
class SettingsRepository:
    def get_all(self) -> dict[str, str]         # returns all overrides
    def get(self, key: str) -> str | None        # single override
    def set(self, key: str, value: str) -> None  # upsert one override
    def delete(self, key: str) -> None           # remove override (reverts to .env/default)
```

Table schema:
```sql
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);
```

#### 2. Settings Service (`services/settings_service.py`)

Orchestrates between `Settings` (pydantic model) and `SettingsRepository`.

- `get_effective_settings()` → merges DB overrides onto `Settings` defaults
- `update_settings(updates: dict)` → validates, persists, returns which keys require restart
- `get_settings_schema()` → returns metadata per field (type, label, group, sensitive, requires_restart)

#### 3. Settings Router (`api/routers/settings.py`)

New endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/settings` | Return all effective settings (sensitive values masked) |
| `PATCH` | `/api/settings` | Update one or more settings |
| `GET` | `/api/settings/schema` | Return field metadata for UI rendering |

#### 4. Startup Integration

In `api/app.py` `create_app()`:
- On startup, load DB overrides and apply them to the `settings` singleton
- The existing `settings = Settings()` in `config.py` remains the default source
- A new `apply_db_overrides()` function in `config.py` patches the singleton from DB values

### Frontend Changes

#### 5. Settings Page (`components/settings/SettingsPage.tsx`)

A new page with grouped config sections:

**Group: Connection (frontend-only, localStorage)**
- API Base URL (the backend URL the frontend talks to)
- This is stored in `localStorage`, not synced via API

**Group: LLM Configuration**
- OpenAI API Key (masked input)
- OpenAI Base URL
- Anthropic API Key (masked input)
- Model name

**Group: Crawler**
- Request Timeout
- Max Concurrent Requests
- RSS Lookback Days

**Group: Storage**
- Data Directory
- Chroma Persist Directory
- Vector TTL Days

**Group: Output**
- Output Directory
- Subscriptions Path

#### 6. Settings API Client (`api/settings.ts`)

New file with:
- `fetchSettings()` → `GET /api/settings`
- `updateSettings(updates)` → `PATCH /api/settings`
- `fetchSettingsSchema()` → `GET /api/settings/schema`

React Query hooks:
- `useSettings()` — reads settings
- `useUpdateSettings()` — mutation with optimistic update

#### 7. Navigation Update

Add "Settings" to `AppShell.tsx` nav bar (after Sources, before theme toggle).

#### 8. Restart Banner

When `requires_restart` settings are changed, show a dismissible banner at the top of the settings page: "Some changes require a server restart to take effect."

## Data Flow

```
Frontend localStorage ──→ API Base URL (client-side only)
                            │
                            ▼
GET /api/settings ──────→ SettingsService.get_effective_settings()
                            │
                            ├── settings DB overrides (if any)
                            └── Settings pydantic defaults (from .env)
                            │
                            ▼
                    Response with masked sensitive values

PATCH /api/settings ───→ SettingsService.update_settings(updates)
                            │
                            ├── Validate each key against Settings model
                            ├── Persist to settings DB table
                            └── Return requires_restart flags
```

## Files to Create/Modify

### New Files
| File | Lines (est.) |
|------|-------------|
| `src/comp_synth/store/repositories/settings_repository.py` | ~80 |
| `src/comp_synth/services/settings_service.py` | ~120 |
| `src/comp_synth/api/routers/settings.py` | ~80 |
| `frontend/src/components/settings/SettingsPage.tsx` | ~250 |
| `frontend/src/components/settings/SettingsGroup.tsx` | ~60 |
| `frontend/src/components/settings/SettingsField.tsx` | ~80 |
| `frontend/src/api/settings.ts` | ~40 |
| `tests/test_settings_api.py` | ~120 |
| `tests/test_settings_service.py` | ~100 |
| `tests/test_settings_repository.py` | ~80 |

### Modified Files
| File | Change |
|------|--------|
| `src/comp_synth/store/migrations.py` | Add `settings` table migration |
| `src/comp_synth/api/app.py` | Register settings router, add startup hook |
| `src/comp_synth/config.py` | Add `apply_db_overrides()` function |
| `frontend/src/App.tsx` | Add `/settings` route |
| `frontend/src/components/layout/AppShell.tsx` | Add Settings nav item |
| `frontend/src/api/hooks.ts` | Import settings hooks |
| `frontend/src/api/types.ts` | Add settings types |

## Implementation Phases

### Phase 1: Backend Foundation
1. Add `settings` table migration to `migrations.py`
2. Create `SettingsRepository` with CRUD operations
3. Create `SettingsService` with merge logic and schema metadata
4. Add `apply_db_overrides()` to `config.py`
5. Write tests for repository and service layers

### Phase 2: API Layer
1. Create settings router with GET/PATCH/schema endpoints
2. Register router in `app.py`
3. Add startup hook to load DB overrides
4. Write API integration tests

### Phase 3: Frontend
1. Add settings types to `api/types.ts`
2. Create settings API client and hooks
3. Build `SettingsField` component (handles text, number, boolean, masked inputs)
4. Build `SettingsGroup` component
5. Build `SettingsPage` with grouped sections
6. Add route and nav item
7. Add restart banner

### Phase 4: Polish
1. Error handling and validation feedback
2. Loading and saving states
3. Responsive layout
4. Dark mode support (inherited from existing theme)

## Scope Decisions

### In Scope
- View/edit all `Settings` fields via UI
- Frontend API base URL stored in `localStorage`
- Sensitive value masking
- Restart-required indicator
- Database persistence (not .env write-back)

### NOT in Scope
- CORS configuration via UI (CORS is a deployment concern, not a runtime setting)
- `.env` file write-back (DB is the runtime source of truth)
- Hot-reload of settings without restart (too complex for initial version)
- Settings change history/audit log
- Import/export settings as JSON/YAML
- Authentication on settings endpoint (assumes single-user/local deployment)

---

## CEO Review Findings (Phase 1)

### Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|----------|
| 1 | CEO | Change key-value table to JSON blob storage | Mechanical | P5 (explicit) | Key-value rows will drift from Pydantic model; JSON blob is validated atomically | Key-value rows |
| 2 | CEO | All settings require restart, not just "some" | Mechanical | P5 (explicit) | Every setting is captured at init time in closures/constructors; no hot-reload exists | Per-field restart flags |
| 3 | CEO | Use absence-based PATCH (only changed fields) | Mechanical | P1 (completeness) | Sending masked values back creates ambiguity; absence = no change | Send full form with masked values |
| 4 | CEO | Keep DB-backed approach over YAML config | Taste | P3 (pragmatic) | DB is already the persistence layer; adding YAML config parsing is a parallel system. YAML alternative is valid for a different deployment model | YAML config file |
| 5 | CEO | Keep Settings page scope, defer observability to future | Mechanical | P6 (bias action) | Observability is a separate feature; settings CRUD is the user's stated request | Build system-status view instead |

### Corrected Premises

3. **All settings require a server restart to take effect.** There is no hot-reload path. The UX is "save → restart." The `requires_restart` concept is removed; it is universal.
4. **Sensitive values are masked in GET responses. PATCH uses absence convention: if a field is absent from the PATCH body, it is unchanged. If present, it is updated (masked value `***` is rejected as invalid).**
5. **Settings are stored as a single JSON blob in SQLite**, not as key-value rows. This enables atomic validation against the Pydantic model.

### What Already Exists

| Sub-problem | Existing Code |
|-------------|---------------|
| Config model | `config.py` — `Settings(BaseSettings)` with all fields |
| SQLite migrations | `store/migrations.py` — lightweight migration framework |
| Repository pattern | `store/repositories/` — article, source, crawl, report repos |
| Service pattern | `services/` — source, article, crawl, dashboard, report services |
| API router pattern | `api/routers/` — articles, sources, crawls, reports, tags, dashboard |
| Frontend page pattern | `components/{feature}/FeaturePage.tsx` — consistent structure |
| API client pattern | `api/client.ts` — `apiGet`, `apiPatch`, `apiPost` helpers |
| React Query hooks | `api/hooks.ts` — hooks for every endpoint |
| UI primitives | `components/ui/` — Badge, EmptyState, ErrorCard, LoadingSkeleton |

### NOT in Scope (CEO additions)
- System observability view (separate feature)
- Hot-reload of any settings
- Per-field `requires_restart` flags (all require restart)
- Config import/export

---

## Design Review Findings (Phase 2)

### Design Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|----------|
| 6 | Design | Reorder groups: LLM first, Crawler second, Advanced (Connection/Storage/Output) last | Mechanical | P1 (completeness) | Usage frequency: LLM keys are highest-touch, Connection is set-once | Keep original order |
| 7 | Design | Card-style group layout, `max-w-3xl` single column | Mechanical | P5 (explicit) | Matches editorial design system; prevents generic SaaS look | Flat label/input rows |
| 8 | Design | Per-group save buttons with "modified" indicator | Taste | P5 (explicit) | Per-group save is more editorial than global save; aligns with section-based editing | Single global save button |
| 9 | Design | Masked fields: show "configured" badge, clear on focus, placeholder "Enter new value" | Mechanical | P1 (completeness) | Prevents accidental masked-value submission; clear mental model | Masked string as input value |
| 10 | Design | Connection section visually distinct with "Frontend · localStorage" label | Mechanical | P5 (explicit) | Prevents confusion when backend is unreachable; clear scope separation | Mixed with other fields |
| 11 | Design | Restart banner persisted in localStorage, visible across pages | Taste | P1 (completeness) | User navigates away and forgets; persistent banner is safer | Dismissible page-only banner |
| 12 | Design | Add "Reset to default" per group, mapping to DELETE override | Mechanical | P2 (boil lakes) | SettingsRepository.delete() already planned; UI for it is in blast radius | No undo capability |
| 13 | Design | Define settings schema response shape in plan | Mechanical | P5 (explicit) | Schema endpoint is useless without a defined contract | Leave schema unspecified |

### Visual Specification

**Layout:** `max-w-3xl` single column, centered. Each group is a card with subtle border (`border-rule`), group title in `font-display text-2xl font-bold`, field labels in `text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4` (matching SourcesPage pattern). Generous vertical spacing (`space-y-8` between groups, `space-y-4` between fields).

**Group order:**
1. LLM Configuration (API keys, base URLs, model) — most frequently edited
2. Crawler (timeout, concurrency, lookback) — moderately edited
3. Advanced (Connection, Storage, Output) — rarely edited, collapsed by default

**Connection group:** Visually distinct card with a subtle background tint and a "Frontend · localStorage" chip, to make it clear this section does not touch the backend API.

**Interaction states (promoted from Phase 4 to core spec):**
- **Loading:** Full-page `LoadingSkeleton` matching existing page patterns
- **First-run / defaults:** Fields show current effective values from `.env`/defaults. No special empty state — values always exist.
- **Saving:** Per-group save button shows spinner, then brief checkmark animation
- **Validation error:** Inline red text below field, field border turns red. No toast.
- **API unreachable:** Connection section still works (localStorage). Other groups show `ErrorCard` from existing UI primitives.
- **Restart needed:** Persistent yellow banner below nav bar (across all pages), dismissible per session

**Masked field interaction:**
- GET response: sensitive fields return `"***configured***"` sentinel
- Frontend renders: label shows "configured" badge (green dot + text), input is empty with placeholder "Enter new value to update"
- PATCH: only sends fields the user actually typed into; absent fields = unchanged

**Settings schema response shape:**
```json
{
  "fields": {
    "openai_api_key": {
      "type": "string",
      "group": "llm",
      "label": "OpenAI API Key",
      "sensitive": true,
      "description": "API key for OpenAI-compatible LLM provider",
      "default": ""
    },
    "request_timeout": {
      "type": "integer",
      "group": "crawler",
      "label": "Request Timeout",
      "description": "HTTP request timeout in seconds",
      "default": 30,
      "constraints": { "minimum": 5, "maximum": 300 }
    }
  }
}
```

---

## Eng Review Findings (Phase 3)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│ Frontend (React)                                    │
│                                                     │
│  localStorage ←── API Base URL (Connection group)   │
│                                                     │
│  SettingsPage ──→ api/settings.ts                   │
│     │              │ useSettings()                   │
│     │              │ useUpdateSettings()             │
│     ▼              ▼                                │
│  SettingsGroup  apiPatch('/api/settings', changes)   │
│  SettingsField                                      │
└──────────────────────┬──────────────────────────────┘
                       │ PATCH (changed fields only)
                       ▼
┌──────────────────────────────────────────────────────┐
│ Backend (FastAPI)                                    │
│                                                      │
│  routers/settings.py ──→ services/settings_service.py│
│    GET /api/settings       │                         │
│    PATCH /api/settings     │ validate against model  │
│    GET /api/settings/schema│ persist JSON blob        │
│                            ▼                         │
│  repositories/settings_repository.py                 │
│    └── SQLite settings table (1 row, JSON blob)      │
│                                                      │
│  config.py ──→ apply_db_overrides() on startup       │
│    │         reads JSON blob, patches Settings()     │
│    ▼                                                 │
│  settings singleton (read by 18+ modules)            │
└──────────────────────────────────────────────────────┘
```

### Eng Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|----------|
| 14 | Eng | Single-row JSON blob in existing `crawl_state.db` | Mechanical | P4 (DRY) | Same DB, migration framework, session pattern as existing repos | Separate config DB |
| 15 | Eng | `apply_db_overrides()` patches `settings.__dict__` on startup before consumers read | Mechanical | P5 (explicit) | All 18+ sites hold a reference to the singleton; patching in-place in `lifespan()` before `yield` ensures all see overrides | Replace module-level object |
| 16 | Eng | PATCH validates via `Settings.model_validate()` before persist | Mechanical | P1 (completeness) | Prevents invalid config that would crash next startup | Trust and store any value |
| 17 | Eng | Reject masked sentinel `***configured***` in PATCH with 422 | Mechanical | P5 (explicit) | Prevents accidental overwrite of secrets | Silently ignore sentinel |
| 18 | Eng | Path fields validated: reject `..` segments, resolve absolute | Mechanical | P1 (completeness) | Prevents writing data to arbitrary filesystem locations | Accept any string |
| 19 | Eng | Settings endpoint unauthenticated (single-user, local-only) | Taste | P3 (pragmatic) | CompSynth is localhost-only; CORS restricts to localhost:5173 | Add auth now |
| 20 | Eng | Full test coverage: repo, service, API, startup, validation, masked rejection, reset | Mechanical | P1 (completeness) | 7 test categories for settings lifecycle | Minimal happy-path tests |

### Security Analysis

| Concern | Risk | Mitigation |
|---------|------|------------|
| API keys in transit | Low — localhost only | Mask in GET; use HTTPS if deployed remotely |
| Unauthenticated PATCH | Low — local-only, CORS | CORS restriction to localhost:5173 |
| Path traversal in storage fields | High | Validate no `..` segments; resolve to absolute; reject outside data root |
| Invalid config breaks startup | High | Validate on write via Pydantic; `apply_db_overrides()` wrapped in try/except with fallback to .env defaults |
| XSS via settings values | Low | Render in input fields, not innerHTML |

### Failure Modes Registry

| Failure | Trigger | Impact | Mitigation |
|---------|---------|--------|------------|
| Startup crash from bad override | Invalid value persisted | Server won't start | Validate on write; fallback in `apply_db_overrides()` |
| DB table missing | Migration not run | GET returns .env defaults, PATCH 503 | `bootstrap_database()` creates table |
| JSON blob corrupted | Manual DB edit / disk error | Same as bad override | try/except parse; delete blob, fall back |
| Overwrite API key with empty | User clears field | LLM calls fail | Empty string is valid ("no key"); UX shows warning |
| Concurrent writes | Two tabs save at once | Last write wins | Acceptable for single-user |

### Test Plan

**`tests/test_settings_repository.py`** — save/load JSON blob, upsert, delete, empty DB returns None
**`tests/test_settings_service.py`** — merge logic, validation (type/sentinel/path), schema metadata
**`tests/test_settings_api.py`** — GET masked, PATCH valid/invalid/sentinel/absence, schema endpoint
**`tests/test_config_overrides.py`** — `apply_db_overrides()` patches singleton, fallback on invalid, startup integration

### "NOT in Scope" (Eng)
- Auth for settings endpoint
- Hot-reload (universal restart)
- Settings version history
- Multi-user conflict resolution

# CompSynth

CompSynth is a local content aggregation pipeline. It reads RSS, static web, and JavaScript-rendered web sources from `subscriptions.yaml`, deduplicates crawled items, enriches them with historical context, and writes Markdown digests to `output/`.

## Requirements

- Python 3.11+
- `uv`
- LLM credentials for summarization and report generation

## Install

```bash
uv sync
```

If `uv` cannot access its cache on Windows, fix the permissions for `%LOCALAPPDATA%\uv\cache` or rerun from a shell that can read and write that directory.

## Configure

Copy the example subscriptions file and edit the source list:

```bash
copy subscriptions.example.yaml subscriptions.yaml
```

Set one LLM provider:

```bash
set COMPSYNTH_OPENAI_API_KEY=...
set COMPSYNTH_OPENAI_BASE_URL=https://api.openai.com/v1
set COMPSYNTH_MODEL=gpt-4o-mini
```

or:

```bash
set COMPSYNTH_ANTHROPIC_API_KEY=...
set COMPSYNTH_MODEL=claude-sonnet-4-20250514
```

## Run

```bash
uv run compsynth
uv run compsynth --help
```

If `subscriptions.yaml` is missing, CompSynth reports that you should copy `subscriptions.example.yaml`.

## Test

```bash
uv run python -m compileall -q src tests
uv run python -m pytest -q
```

## Source Types

`selectors` may be either a single mapping or a list of mappings. Lists are recommended.

```yaml
sources:
  - type: rss
    name: Example Feed
    url: https://example.com/feed.xml

  - type: web
    name: Example Site
    url: https://example.com/
    selectors:
      - item_container: article
        url: a
        title: h2
        summary: p

  - type: javascript
    name: Example App
    url: https://example.com/app
    javascript: true
```

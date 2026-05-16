# INSTALL.md — Agent Installation Guide

> This document is designed for Coding Agents (Claude Code, Cursor, Copilot Workspace, etc.)
> to set up the CompSynth project. Follow each step in order. Every step has a **verify**
> instruction — do not proceed until verification passes.

## Prerequisites

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| Python | 3.11+ | Runtime |
| uv | latest | Package manager |
| Node.js | 18+ | Frontend (optional) |
| npm | 9+ | Frontend dependencies (optional) |

## Steps

### 1. Clone and enter project directory

```bash
git clone https://github.com/ADchampion3/CompSynth.git
cd CompSynth
```

**Verify:** `test -f pyproject.toml && echo OK`

---

### 2. Ensure uv is installed

Run the following command to check:

```bash
uv --version
```

**If the command succeeds**, uv is available. Proceed to step 3.

**If the command fails** (`command not found`, `not recognized`, etc.), install uv:

- **Linux / macOS:**

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

  After installation, source the shell profile or use the full path:
  ```bash
  export PATH="$HOME/.local/bin:$PATH"
  ```

- **Windows (PowerShell):**

  ```powershell
  powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

  After installation, refresh PATH:
  ```powershell
  $env:PATH = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
  ```

**Verify:** `uv --version` prints a version number.

> **Note for agents:** Do NOT ask the user for the uv path. If uv is not in PATH after
> installation, check these common locations:
> - Linux/macOS: `~/.local/bin/uv`, `~/.cargo/bin/uv`
> - Windows: `%USERPROFILE%\.local\bin\uv.exe`, `%LOCALAPPDATA%\uv\uv.exe`

---

### 3. Install Python dependencies

```bash
uv sync
```

**Verify:** `uv run python -c "import comp_synth; print('OK')"` or `test -d .venv && echo OK`

> This creates a `.venv/` in the project root and installs all dependencies from `pyproject.toml`.

---

### 4. Create configuration files

**4a. Create `.env` from example (if `.env` does not exist):**

```bash
test -f .env || cp .env.example .env
```

**4b. Create `subscriptions.yaml` from example (if it does not exist):**

```bash
test -f subscriptions.yaml || cp subscriptions.example.yaml subscriptions.yaml
```

**Verify:** `test -f .env && test -f subscriptions.yaml && echo OK`

> **Do NOT fill in API keys or secrets.** The user must configure `.env` themselves.
> Leave a message telling the user to edit `.env` with their LLM API key.

---

### 5. Create runtime directories

```bash
mkdir -p data logs output
```

**Verify:** `test -d data && test -d logs && test -d output && echo OK`

---

### 6. Verify the CLI

```bash
uv run compsynth --version
```

**Verify:** Prints a version string like `compsynth 0.1.0`.

---

### 7. Run health check

```bash
uv run compsynth doctor
```

This checks Python version, `.env`, API keys, database paths, and SMTP config.
Some items will show warnings because API keys are not yet configured — this is expected.

**Verify:** Command exits. Review output for any `FATAL` items.

---

### 8. (Optional) Install frontend dependencies

Only if the user requested frontend setup, or if `frontend/package.json` exists:

```bash
cd frontend && npm install && cd ..
```

**Verify:** `test -d frontend/node_modules && echo OK`

---

## Post-Install Summary

After all steps complete, report the following to the user:

```
CompSynth setup complete.

Next steps:
1. Edit .env — add your LLM API key (COMPSYNTH_OPENAI_API_KEY or COMPSYNTH_ANTHROPIC_API_KEY)
2. Edit subscriptions.yaml — add your RSS/Web sources
3. Start backend:  uv run compsynth serve
4. Start frontend: cd frontend && npm run dev (if installed)
5. Open http://localhost:5173
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `uv sync` fails with resolver error | Check Python version >= 3.11: `python --version` |
| `uv` not found after install | Restart terminal, or use full path from step 2 note |
| `compsynth --version` fails | Run `uv run python -m compileall -q src` to check for import errors |
| `npm install` fails | Ensure Node.js 18+: `node --version` |
| `.env` missing | `cp .env.example .env` |
| `subscriptions.yaml` missing | `cp subscriptions.example.yaml subscriptions.yaml` |

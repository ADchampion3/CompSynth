"""CompSynth CLI — root Typer app with all commands."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from importlib.metadata import version as pkg_version
from pathlib import Path

import typer

from comp_synth.cli.exit_codes import EXIT_FATAL, EXIT_PARTIAL, EXIT_SUCCESS
from comp_synth.utils.logging import CONSOLE_FMT, logger

app = typer.Typer(
    name="compsynth",
    add_completion=False,
    help="CompSynth — content aggregation and publishing system.",
)

reports_app = typer.Typer(help="Read generated report metadata.")
sources_app = typer.Typer(help="Manage subscription sources.")
config_app = typer.Typer(help="Show current configuration.")

app.add_typer(reports_app, name="reports")
app.add_typer(sources_app, name="sources")
app.add_typer(config_app, name="config")


# ── helpers ──────────────────────────────────────────────────────────────────

def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"compsynth {pkg_version('compsynth')}")
        raise typer.Exit()


def _mask_secret(value: str) -> str:
    return "****" + value[-4:] if len(value) > 4 else "****"


def _compute_exit_code(result: dict) -> int:
    errors = result.get("errors", [])
    if not errors:
        return EXIT_SUCCESS
    source_runs = result.get("source_runs", [])
    if source_runs:
        total = len(source_runs)
        failed = sum(1 for s in source_runs if s.get("status") == "failed")
        if total > 0 and failed / total > 0.3:
            return EXIT_PARTIAL
    elif errors:
        return EXIT_PARTIAL
    return EXIT_SUCCESS


def _get_cron_mode(ctx: typer.Context) -> bool:
    current = ctx
    while current:
        if current.params.get("cron"):
            return True
        current = current.parent
    return os.environ.get("COMPSYNTH_CRON", "").strip() in ("1", "true", "yes")


def _get_db_path(ctx: typer.Context) -> Path | None:
    """Walk up context tree to find --db-path from root callback."""
    current = ctx
    while current:
        if "db_path" in current.params:
            val = current.params["db_path"]
            return Path(val) if val is not None and not isinstance(val, Path) else val
        current = current.parent
    return None


# ── root callback ────────────────────────────────────────────────────────────

@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show debug-level output."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress non-error output (still shows JSON summary)."),
    cron: bool = typer.Option(False, "--cron", help="Cron mode: suppress JSON summary on success. Implied by COMPSYNTH_CRON=1."),
    version: bool | None = typer.Option(None, "--version", "-V", callback=_version_callback, is_eager=True, help="Print version and exit."),
    db_path: Path | None = typer.Option(None, "--db-path", help="SQLite crawl state database path."),
) -> None:
    cron_env = os.environ.get("COMPSYNTH_CRON", "").strip() in ("1", "true", "yes")
    if verbose:
        level = "DEBUG"
    elif quiet:
        level = "WARNING"
    elif cron or cron_env:
        level = "WARNING"
    else:
        level = "INFO"
    logger.remove()
    logger.add(sys.stderr, level=level, format=CONSOLE_FMT, colorize=sys.stderr.isatty(), diagnose=True, backtrace=True)


# ── default pipeline (no subcommand) ─────────────────────────────────────────

@app.command("default", hidden=True)
def run_default(ctx: typer.Context) -> None:
    """Run the full pipeline: crawl, dedup, summarize, publish, notify."""
    from comp_synth.main import run as async_run

    db_path = _get_db_path(ctx)
    try:
        result = asyncio.run(async_run(db_path))
    except Exception:
        logger.exception("Fatal pipeline error")
        raise typer.Exit(code=EXIT_FATAL)

    exit_code = _compute_exit_code(result)
    payload = _crawl_result_to_dict(result)

    if not _get_cron_mode(ctx):
        typer.echo(json.dumps(payload, ensure_ascii=False))
    raise typer.Exit(code=exit_code)


# ── crawl ────────────────────────────────────────────────────────────────────

@app.command()
def crawl(ctx: typer.Context) -> None:
    """Run crawl pipeline and print summary JSON."""
    from comp_synth.main import run as async_run

    db_path = _get_db_path(ctx)
    try:
        result = asyncio.run(async_run(db_path))
    except Exception:
        logger.exception("Fatal crawl error")
        raise typer.Exit(code=EXIT_FATAL)

    exit_code = _compute_exit_code(result)
    payload = _crawl_result_to_dict(result)

    if not _get_cron_mode(ctx):
        typer.echo(json.dumps(payload, ensure_ascii=False))
    raise typer.Exit(code=exit_code)


# ── serve ────────────────────────────────────────────────────────────────────

@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host."),
    port: int = typer.Option(8000, "--port", help="Bind port."),
) -> None:
    """Start the CompSynth HTTP API server."""
    import uvicorn

    from comp_synth.api.app import create_app

    uvicorn.run(create_app(), host=host, port=port, reload=False)


# ── dashboard ────────────────────────────────────────────────────────────────

@app.command()
def dashboard(ctx: typer.Context) -> None:
    """Print dashboard summary JSON."""
    from comp_synth.main import dashboard as _dashboard

    db_path = _get_db_path(ctx)
    result = _dashboard(db_path)
    typer.echo(json.dumps(result, ensure_ascii=False))


# ── reports ──────────────────────────────────────────────────────────────────

@reports_app.command("list")
def reports_list(ctx: typer.Context) -> None:
    """List generated reports."""
    from comp_synth.main import reports_command

    db_path = _get_db_path(ctx)
    args = _Namespace(report_command="list", db_path=db_path)
    result = reports_command(args)
    typer.echo(json.dumps(result, ensure_ascii=False))


@reports_app.command("get")
def reports_get(
    report_id: str = typer.Argument(help="Report id such as digest_20260201."),
    ctx: typer.Context = typer.Context,
) -> None:
    """Read one generated report."""
    from comp_synth.main import reports_command

    db_path = _get_db_path(ctx)
    args = _Namespace(report_command="get", report_id=report_id, db_path=db_path)
    result = reports_command(args)
    typer.echo(json.dumps(result, ensure_ascii=False))


# ── sources ──────────────────────────────────────────────────────────────────

@sources_app.command("import")
def sources_import(
    path: Path | None = typer.Option(None, "--path", help="Subscriptions YAML path."),
    ctx: typer.Context = typer.Context,
) -> None:
    """Import subscriptions YAML into SQLite."""
    from comp_synth.main import sources_command

    db_path = _get_db_path(ctx)
    args = _Namespace(source_command="import", path=path, db_path=db_path)
    result = sources_command(args)
    typer.echo(json.dumps(result, ensure_ascii=False))


@sources_app.command("export")
def sources_export(
    output: Path | None = typer.Option(None, "--output", help="Output YAML path."),
    ctx: typer.Context = typer.Context,
) -> None:
    """Export SQLite sources to YAML."""
    from comp_synth.main import sources_command

    db_path = _get_db_path(ctx)
    args = _Namespace(source_command="export", output=output, db_path=db_path)
    result = sources_command(args)
    typer.echo(json.dumps(result, ensure_ascii=False))


# ── notify ───────────────────────────────────────────────────────────────────

@app.command()
def notify(
    file: Path | None = typer.Option(None, "--file", help="Specific Markdown file to send."),
) -> None:
    """Send digest via configured notification channels."""
    from comp_synth.main import notify_command

    args = _Namespace(file=file)
    result = notify_command(args)
    typer.echo(json.dumps(result, ensure_ascii=False))


# ── status ───────────────────────────────────────────────────────────────────

@app.command()
def status(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Show system health at a glance."""
    from comp_synth.config import settings
    from comp_synth.main import dashboard as _dashboard

    db_path = _get_db_path(ctx)
    try:
        summary = _dashboard(db_path)
    except Exception:
        logger.exception("Failed to read status")
        raise typer.Exit(code=EXIT_FATAL)

    if json_output:
        typer.echo(json.dumps(summary, ensure_ascii=False, default=str))
        has_unhealthy = bool(summary.get("unhealthy_sources")) or bool(summary.get("failed_sources"))
        raise typer.Exit(code=EXIT_PARTIAL if has_unhealthy else EXIT_SUCCESS)

    # Human-readable output
    active = summary.get("article_count", 0)
    unhealthy = summary.get("unhealthy_sources", [])
    failed = summary.get("failed_sources", [])
    last_run = summary.get("latest_crawl_run")

    lines: list[str] = []
    lines.append(f"Sources: {active} articles tracked, {len(unhealthy)} unhealthy")

    if last_run:
        started = last_run.get("started_at", "unknown")
        run_status = last_run.get("status", "unknown")
        new_items = last_run.get("new_items", 0)
        lines.append(f"Last crawl: {started} — {run_status}, {new_items} new items")
    else:
        lines.append("Last crawl: never")

    # Check for latest digest
    output_dir = Path(settings.output_dir)
    digests = sorted(output_dir.glob("digest_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if digests:
        lines.append(f"Digest: {digests[0]}")
    else:
        lines.append("Digest: none found")

    if failed:
        lines.append(f"Errors: {len(failed)} sources failed (run `compsynth logs --last` for details)")

    typer.echo("\n".join(lines))
    has_issues = bool(unhealthy) or bool(failed)
    raise typer.Exit(code=EXIT_PARTIAL if has_issues else EXIT_SUCCESS)


# ── logs ─────────────────────────────────────────────────────────────────────

@app.command("logs")
def logs_cmd(
    last: bool = typer.Option(True, "--last", help="Show the most recent log file."),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show."),
    level: str | None = typer.Option(None, "--level", "-l", help="Filter by level (DEBUG, INFO, WARNING, ERROR)."),
) -> None:
    """View log files."""
    from comp_synth.config import settings

    log_dir = settings.log_dir.resolve()
    if not log_dir.exists():
        typer.echo(f"Log directory not found: {log_dir}", err=True)
        raise typer.Exit(code=EXIT_PARTIAL)

    # Find the most recent app log file
    log_files = sorted(log_dir.glob("app_*.log"), reverse=True)
    if not log_files:
        typer.echo("No log files found.", err=True)
        raise typer.Exit(code=EXIT_PARTIAL)

    log_path = log_files[0].resolve()

    # Path traversal protection
    if not str(log_path).startswith(str(log_dir)):
        typer.echo("Invalid log path.", err=True)
        raise typer.Exit(code=EXIT_FATAL)

    try:
        all_lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        typer.echo(f"Cannot read log file: {exc}", err=True)
        raise typer.Exit(code=EXIT_PARTIAL)

    # Filter by level if specified
    if level:
        level_upper = level.upper()
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if level_upper not in valid_levels:
            typer.echo(f"Invalid level '{level}'. Valid: {', '.join(sorted(valid_levels))}", err=True)
            raise typer.Exit(code=EXIT_FATAL)
        all_lines = [ln for ln in all_lines if f"| {level_upper:<8} |" in ln]

    # Tail N lines
    tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
    typer.echo("\n".join(tail))
    raise typer.Exit(code=EXIT_SUCCESS)


# ── config show ──────────────────────────────────────────────────────────────

@config_app.command("show")
def config_show() -> None:
    """Print current effective configuration (secrets masked)."""
    from comp_synth.config import settings

    sensitive_patterns = {"key", "password", "secret", "token"}

    model_fields = type(settings).model_fields
    lines: list[str] = []
    for field_name in model_fields:
        value = getattr(settings, field_name, None)
        display_value: str
        if any(p in field_name.lower() for p in sensitive_patterns):
            s = str(value) if value is not None else ""
            display_value = _mask_secret(s) if s else "(not set)"
        else:
            display_value = str(value) if value is not None else "(not set)"
        label = field_name
        lines.append(f"{label:>30s}: {display_value}")

    typer.echo("\n".join(lines))


# ── doctor ───────────────────────────────────────────────────────────────────

@app.command()
def doctor(
    required_only: bool = typer.Option(False, "--required-only", help="Skip optional checks (for cron health checks)."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Validate the setup and print a checklist."""
    import platform

    from comp_synth.config import settings

    checks: list[dict] = []
    has_failure = False

    # 1. Python version
    py_ver = platform.python_version()
    py_ok = tuple(int(x) for x in py_ver.split(".")[:2]) >= (3, 11)
    checks.append({"name": "Python 3.11+", "ok": py_ok, "detail": f"Python {py_ver}", "required": True})
    if not py_ok:
        has_failure = True

    # 2. .env file
    env_path = Path(".env")
    env_ok = env_path.exists()
    checks.append({"name": ".env file", "ok": env_ok, "detail": "found" if env_ok else "not found", "required": True})
    if not env_ok:
        has_failure = True

    # 3. Required API key (depends on provider)
    provider = settings.llm_provider
    if provider == "openai":
        key_value = settings.openai_api_key
        key_name = "COMPSYNTH_OPENAI_API_KEY"
    elif provider == "anthropic":
        key_value = settings.anthropic_api_key
        key_name = "COMPSYNTH_ANTHROPIC_API_KEY"
    else:
        key_value = ""
        key_name = f"COMPSYNTH_{provider.upper()}_API_KEY"
    key_ok = bool(key_value)
    checks.append({"name": key_name, "ok": key_ok, "detail": "set" if key_ok else "not set", "required": True})
    if not key_ok:
        has_failure = True

    # 4. subscriptions.yaml
    sub_path = settings.subscriptions_path
    sub_ok = sub_path.exists()
    sub_detail = str(sub_path)
    if sub_ok:
        try:
            import yaml

            with open(sub_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            source_count = len(data.get("sources", [])) if data else 0
            sub_detail = f"found ({source_count} sources)"
        except Exception:
            sub_ok = False
            sub_detail = f"parse error in {sub_path}"
    checks.append({"name": "subscriptions.yaml", "ok": sub_ok, "detail": sub_detail, "required": True})
    if not sub_ok:
        has_failure = True

    # 5. SQLite crawl_state.db
    db_path = settings.crawl_db_path
    db_ok = db_path.parent.exists()
    if db_ok and db_path.exists():
        try:
            db_path.stat()
            db_detail = f"accessible ({db_path})"
        except OSError as exc:
            db_ok = False
            db_detail = f"error: {exc}"
    elif db_ok:
        db_detail = f"parent dir exists, DB will be created ({db_path})"
    else:
        db_detail = f"parent dir not found ({db_path})"
    checks.append({"name": "SQLite DB", "ok": db_ok, "detail": db_detail, "required": True})
    if not db_ok:
        has_failure = True

    # 6. Log directory writable
    log_dir = settings.log_dir
    log_ok = log_dir.exists()
    if log_ok:
        try:
            test_file = log_dir / ".doctor_write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()
            log_detail = f"writable ({log_dir})"
        except OSError:
            log_ok = False
            log_detail = f"not writable ({log_dir})"
    else:
        log_detail = f"not found ({log_dir})"
    checks.append({"name": "Log directory", "ok": log_ok, "detail": log_detail, "required": True})
    if not log_ok:
        has_failure = True

    # 7. SMTP (if email channel configured) — optional
    channels = settings.get_channels()
    if "email" in channels:
        smtp_fields = [settings.smtp_host, settings.smtp_user, settings.smtp_to]
        smtp_ok = all(smtp_fields)
        smtp_detail = "configured" if smtp_ok else "incomplete SMTP settings"
        checks.append({"name": "SMTP", "ok": smtp_ok, "detail": smtp_detail, "required": False})
    else:
        checks.append({"name": "SMTP", "ok": True, "detail": "not needed (no email channel)", "required": False})

    # 8. Optional API keys
    if not required_only:
        if provider != "anthropic":
            anthropic_ok = bool(settings.anthropic_api_key)
            checks.append({"name": "COMPSYNTH_ANTHROPIC_API_KEY", "ok": anthropic_ok, "detail": "set" if anthropic_ok else "not set (optional)", "required": False})
        if provider != "openai":
            openai_ok = bool(settings.openai_api_key)
            checks.append({"name": "COMPSYNTH_OPENAI_API_KEY", "ok": openai_ok, "detail": "set" if openai_ok else "not set (optional)", "required": False})

    # Output
    if json_output:
        typer.echo(json.dumps({"checks": checks, "ok": not has_failure}, ensure_ascii=False))
        raise typer.Exit(code=EXIT_PARTIAL if has_failure else EXIT_SUCCESS)

    for check in checks:
        if required_only and not check["required"]:
            continue
        mark = "+" if check["ok"] else "X"
        suffix = f" ({check['detail']})" if check["detail"] else ""
        optional_tag = " (optional)" if not check["required"] else ""
        typer.echo(f"[{mark}] {check['name']}{optional_tag}{suffix}")

    raise typer.Exit(code=EXIT_PARTIAL if has_failure else EXIT_SUCCESS)


# ── internal helpers ─────────────────────────────────────────────────────────

class _Namespace:
    """Simple namespace for passing args to backward-compat command functions."""

    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


def _crawl_result_to_dict(result: dict) -> dict:
    publish_results = result.get("publish_results", {}) or {}
    items = result.get("new_items") or result.get("fetched_items") or result.get("raw_items") or []
    return {
        "crawl_run_id": result.get("crawl_run_id"),
        "status": publish_results.get("status", "unknown"),
        "new_items": len(items),
        "errors": [str(error) for error in result.get("errors", [])],
        "publish_path": publish_results.get("path"),
    }

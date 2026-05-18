"""Tests for the Typer-based CLI (new commands, flags, exit codes)."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from comp_synth.cli.app import app

runner = CliRunner()


# ── --version ────────────────────────────────────────────────────────────────

def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "compsynth" in result.output


# ── --verbose / --quiet / --cron flags ──────────────────────────────────────

def test_verbose_flag_sets_debug_level():
    with patch("comp_synth.cli.app.configure") as mock_configure:
        result = runner.invoke(app, ["--verbose", "config", "show"])
        assert result.exit_code == 0
        mock_configure.assert_called_with(console_level="DEBUG")


def test_quiet_flag_sets_warning_level():
    with patch("comp_synth.cli.app.configure") as mock_configure:
        result = runner.invoke(app, ["--quiet", "config", "show"])
        assert result.exit_code == 0
        mock_configure.assert_called_with(console_level="WARNING")


def test_cron_flag_sets_warning_level():
    with patch("comp_synth.cli.app.configure") as mock_configure:
        result = runner.invoke(app, ["--cron", "config", "show"])
        assert result.exit_code == 0
        mock_configure.assert_called_with(console_level="WARNING")


def test_cron_env_var_sets_warning_level(monkeypatch):
    monkeypatch.setenv("COMPSYNTH_CRON", "1")
    with patch("comp_synth.cli.app.configure") as mock_configure:
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        mock_configure.assert_called_with(console_level="WARNING")


# ── config show ──────────────────────────────────────────────────────────────

def test_config_show_masks_secrets():
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    # API keys should be masked
    assert "api_key" in result.output.lower() or "openai_api_key" in result.output
    # Should not contain full key values (masking pattern is ****XXXX)
    lines = result.output.strip().split("\n")
    for line in lines:
        if "password" in line.lower() or "key" in line.lower():
            # Should contain **** masking
            assert "****" in line or "(not set)" in line


def test_config_show_has_all_fields():
    from comp_synth.config import settings

    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    for field_name in type(settings).model_fields:
        assert field_name in result.output


# ── doctor ───────────────────────────────────────────────────────────────────

def test_doctor_runs():
    result = runner.invoke(app, ["doctor"])
    # May be 0 or 1 depending on environment, should not crash
    assert result.exit_code in (0, 1)
    assert "Python" in result.output


def test_doctor_required_only():
    result = runner.invoke(app, ["doctor", "--required-only"])
    assert result.exit_code in (0, 1)
    # Should not show optional items
    assert "optional" not in result.output.lower() or result.exit_code == 0


def test_doctor_json_output():
    import json

    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code in (0, 1)
    data = json.loads(result.output)
    assert "checks" in data
    assert "ok" in data
    assert isinstance(data["checks"], list)


# ── status ───────────────────────────────────────────────────────────────────

def test_status_shows_summary():
    result = runner.invoke(app, ["status"])
    # May be 0 or 1 depending on environment
    assert result.exit_code in (0, 1)
    assert "Sources:" in result.output
    assert "Last crawl:" in result.output


def test_status_json_output():
    import json

    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code in (0, 1)
    data = json.loads(result.output)
    assert "article_count" in data
    assert "latest_crawl_run" in data


# ── logs ─────────────────────────────────────────────────────────────────────

def test_logs_no_log_dir(tmp_path, monkeypatch):
    from comp_synth.config import settings

    monkeypatch.setattr(settings, "log_dir", tmp_path / "nonexistent")
    result = runner.invoke(app, ["logs"])
    assert result.exit_code == 1


def test_logs_with_log_files(tmp_path, monkeypatch):
    from comp_synth.config import settings

    monkeypatch.setattr(settings, "log_dir", tmp_path)
    log_file = tmp_path / "app_20260516.log"
    log_file.write_text("line1\nline2\nline3\n", encoding="utf-8")
    result = runner.invoke(app, ["logs", "--last", "--lines", "2"])
    assert result.exit_code == 0
    assert "line2" in result.output
    assert "line3" in result.output


def test_logs_level_filter(tmp_path, monkeypatch):
    from comp_synth.config import settings

    monkeypatch.setattr(settings, "log_dir", tmp_path)
    log_file = tmp_path / "app_20260516.log"
    log_file.write_text(
        "2026-05-16 10:00:00.000 | INFO     | test | line1\n"
        "2026-05-16 10:00:01.000 | ERROR    | test | line2\n"
        "2026-05-16 10:00:02.000 | INFO     | test | line3\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["logs", "--level", "ERROR"])
    assert result.exit_code == 0
    assert "ERROR" in result.output
    assert "INFO" not in result.output


def test_logs_invalid_level():
    result = runner.invoke(app, ["logs", "--level", "INVALID"])
    assert result.exit_code == 2


# ── exit codes ───────────────────────────────────────────────────────────────

def test_exit_code_success():
    from comp_synth.cli.app import _compute_exit_code

    result = {"errors": [], "source_runs": []}
    assert _compute_exit_code(result) == 0


def test_exit_code_partial():
    from comp_synth.cli.app import _compute_exit_code

    # >30% failure rate: 4 total, 2 failed = 50%
    result = {
        "errors": ["err1", "err2"],
        "source_runs": [
            {"status": "success"},
            {"status": "success"},
            {"status": "failed"},
            {"status": "failed"},
        ],
    }
    assert _compute_exit_code(result) == 1


def test_exit_code_below_threshold():
    from comp_synth.cli.app import _compute_exit_code

    # 25% failure rate: 4 total, 1 failed = 25% (< 30%)
    result = {
        "errors": ["err1"],
        "source_runs": [
            {"status": "success"},
            {"status": "success"},
            {"status": "success"},
            {"status": "failed"},
        ],
    }
    assert _compute_exit_code(result) == 0


def test_exit_code_fatal():
    from comp_synth.cli.exit_codes import EXIT_FATAL

    assert EXIT_FATAL == 2


# ── secret masking ──────────────────────────────────────────────────────────

def test_mask_secret():
    from comp_synth.cli.app import _mask_secret

    assert _mask_secret("sk-abc123xyz") == "****3xyz"
    assert _mask_secret("abcd") == "****"
    assert _mask_secret("") == "****"


# ── help text ────────────────────────────────────────────────────────────────

def test_help_shows_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "crawl" in result.output
    assert "status" in result.output
    assert "logs" in result.output
    assert "doctor" in result.output
    assert "config" in result.output


def test_subcommand_help():
    result = runner.invoke(app, ["reports", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "get" in result.output

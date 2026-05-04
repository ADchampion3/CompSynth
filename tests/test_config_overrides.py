"""Tests for apply_db_overrides in config.py."""

from comp_synth.config import apply_db_overrides, settings


def test_apply_overrides_patches_singleton():
    original_model = settings.model
    apply_db_overrides({"model": "gpt-4-test"})
    assert settings.model == "gpt-4-test"
    settings.model = original_model


def test_apply_overrides_converts_types():
    original = settings.request_timeout
    apply_db_overrides({"request_timeout": "120"})
    assert settings.request_timeout == 120
    assert isinstance(settings.request_timeout, int)
    settings.request_timeout = original


def test_apply_overrides_path_field():
    original = settings.data_dir
    apply_db_overrides({"data_dir": "/tmp/test-data"})
    assert str(settings.data_dir) == "/tmp/test-data"
    settings.data_dir = original


def test_apply_overrides_bool_field():
    original = settings.selector_zero_refresh_enabled
    apply_db_overrides({"selector_zero_refresh_enabled": "false"})
    assert settings.selector_zero_refresh_enabled is False
    settings.selector_zero_refresh_enabled = original


def test_apply_overrides_skips_invalid():
    original = settings.request_timeout
    apply_db_overrides({"request_timeout": "not_a_number"})
    assert settings.request_timeout == original


def test_apply_overrides_skips_unknown_keys():
    original_model = settings.model
    apply_db_overrides({"nonexistent_field": "value"})
    assert settings.model == original_model

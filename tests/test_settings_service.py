import pytest

from comp_synth.config import settings
from comp_synth.services.settings_service import MASKED_SENTINEL, SettingsService


@pytest.fixture(autouse=True)
def _restore_settings():
    """Snapshot and restore the global settings singleton around each test."""
    snapshot = settings.model_dump()
    yield
    for key, value in snapshot.items():
        if hasattr(settings, key):
            setattr(settings, key, value)


def test_get_effective_returns_defaults():
    svc = SettingsService()
    result = svc.get_effective_settings()
    assert "model" in result
    assert "request_timeout" in result


def test_sensitive_fields_masked():
    svc = SettingsService()
    svc.update_settings({"openai_api_key": "sk-real-key"})
    result = svc.get_effective_settings()
    assert result["openai_api_key"] == MASKED_SENTINEL


def test_update_persists_and_masks():
    svc = SettingsService()
    import unittest.mock
    with unittest.mock.patch("comp_synth.services.settings_service._sync_to_env"):
        result = svc.update_settings({"model": "gpt-4", "openai_api_key": "sk-test"})
    assert result["model"] == "gpt-4"
    assert result["openai_api_key"] == MASKED_SENTINEL


def test_reject_masked_sentinel():
    svc = SettingsService()
    with pytest.raises(Exception) as exc_info:
        svc.update_settings({"openai_api_key": MASKED_SENTINEL})
    assert exc_info.value.status_code == 422


def test_reject_unknown_field():
    svc = SettingsService()
    with pytest.raises(Exception) as exc_info:
        svc.update_settings({"nonexistent_field": "value"})
    assert exc_info.value.status_code == 422


def test_reject_path_traversal():
    svc = SettingsService()
    with pytest.raises(Exception) as exc_info:
        svc.update_settings({"data_dir": "/tmp/../etc"})
    assert exc_info.value.status_code == 422


def test_schema_returns_field_metadata():
    svc = SettingsService()
    schema = svc.get_schema()
    assert "fields" in schema
    assert "model" in schema["fields"]
    assert schema["fields"]["openai_api_key"]["sensitive"] is True
    assert schema["fields"]["model"]["group"] == "llm"


def test_reset_group_reverts_to_defaults():
    import unittest.mock
    svc = SettingsService()
    with unittest.mock.patch("comp_synth.services.settings_service._sync_to_env"):
        svc.update_settings({"model": "gpt-4", "request_timeout": "60"})
    assert settings.model == "gpt-4"

    with unittest.mock.patch("comp_synth.services.settings_service._sync_to_env"):
        result = svc.reset_group("llm")

    # model should revert to Settings default, not stay "gpt-4"
    assert result["model"] != "gpt-4"
    # request_timeout was in "crawler" group, should still be "60"
    assert result["request_timeout"] == "60"


def test_update_validates_against_model():
    svc = SettingsService()
    with pytest.raises(Exception) as exc_info:
        svc.update_settings({"request_timeout": "not_a_number"})
    assert exc_info.value.status_code == 422


def test_absence_based_patch():
    """Updating one field must not clobber another that was set earlier."""
    import unittest.mock
    svc = SettingsService()
    with unittest.mock.patch("comp_synth.services.settings_service._sync_to_env"):
        svc.update_settings({"model": "gpt-4"})
        result = svc.update_settings({"request_timeout": "60"})
    assert result["model"] == "gpt-4"
    assert result["request_timeout"] == "60"


# --- .env sync ---


def test_sync_to_env_updates_existing_key(tmp_path):
    env = tmp_path / ".env"
    env.write_text("COMPSYNTH_MODEL=gpt-3.5\nCOMPSYNTH_REQUEST_TIMEOUT=30\n", encoding="utf-8")

    from comp_synth.services.settings_service import _sync_to_env
    _sync_to_env({"model": "gpt-4"}, env_path=env)

    text = env.read_text(encoding="utf-8")
    assert "COMPSYNTH_MODEL=gpt-4" in text
    assert "COMPSYNTH_REQUEST_TIMEOUT=30" in text


def test_sync_to_env_adds_new_key(tmp_path):
    env = tmp_path / ".env"
    env.write_text("COMPSYNTH_MODEL=gpt-4\n", encoding="utf-8")

    from comp_synth.services.settings_service import _sync_to_env
    _sync_to_env({"model": "gpt-4", "request_timeout": "60"}, env_path=env)

    text = env.read_text(encoding="utf-8")
    assert "COMPSYNTH_MODEL=gpt-4" in text
    assert "COMPSYNTH_REQUEST_TIMEOUT=60" in text


def test_sync_to_env_preserves_unmanaged_keys(tmp_path):
    env = tmp_path / ".env"
    env.write_text("COMPSYNTH_MODEL=gpt-4\nCOMPSYNTH_REQUEST_TIMEOUT=60\n", encoding="utf-8")

    from comp_synth.services.settings_service import _sync_to_env

    _sync_to_env({"model": "gpt-4o"}, env_path=env)

    text = env.read_text(encoding="utf-8")
    assert "COMPSYNTH_MODEL=gpt-4o" in text
    assert "COMPSYNTH_REQUEST_TIMEOUT=60" in text


def test_sync_to_env_removes_explicit_keys(tmp_path):
    env = tmp_path / ".env"
    env.write_text("COMPSYNTH_MODEL=gpt-4\nCOMPSYNTH_REQUEST_TIMEOUT=60\n", encoding="utf-8")

    from comp_synth.services.settings_service import _sync_to_env

    _sync_to_env({}, remove_keys={"model"}, env_path=env)

    text = env.read_text(encoding="utf-8")
    assert "COMPSYNTH_MODEL" not in text
    assert "COMPSYNTH_REQUEST_TIMEOUT=60" in text


def test_sync_to_env_preserves_unmanaged_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# comment\nMY_OTHER_VAR=hello\nCOMPSYNTH_MODEL=gpt-3.5\n", encoding="utf-8")

    from comp_synth.services.settings_service import _sync_to_env
    _sync_to_env({"model": "gpt-4"}, env_path=env)

    text = env.read_text(encoding="utf-8")
    assert "# comment" in text
    assert "MY_OTHER_VAR=hello" in text
    assert "COMPSYNTH_MODEL=gpt-4" in text


def test_sync_to_env_creates_file_if_missing(tmp_path):
    env = tmp_path / "subdir" / ".env"

    from comp_synth.services.settings_service import _sync_to_env
    _sync_to_env({"model": "gpt-4"}, env_path=env)

    assert env.exists()
    text = env.read_text(encoding="utf-8")
    assert "COMPSYNTH_MODEL=gpt-4" in text

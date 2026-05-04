import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from comp_synth.services.settings_service import MASKED_SENTINEL, SettingsService
from comp_synth.store.migrations import bootstrap_database
from comp_synth.store.repositories.settings_repository import SettingsRepository


def _make_service():
    engine = create_engine("sqlite:///:memory:")
    bootstrap_database(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    repo = SettingsRepository(session)
    return SettingsService(repo), session


def test_get_effective_returns_defaults():
    svc, session = _make_service()
    settings = svc.get_effective_settings()
    # Values come from Settings() which reads .env; just verify keys exist
    assert "model" in settings
    assert "request_timeout" in settings


def test_sensitive_fields_masked():
    svc, session = _make_service()
    svc.update_settings({"openai_api_key": "sk-real-key"})
    session.commit()
    settings = svc.get_effective_settings()
    assert settings["openai_api_key"] == MASKED_SENTINEL


def test_update_persists_and_masks():
    svc, session = _make_service()
    result = svc.update_settings({"model": "gpt-4", "openai_api_key": "sk-test"})
    session.commit()
    assert result["model"] == "gpt-4"
    assert result["openai_api_key"] == MASKED_SENTINEL


def test_reject_masked_sentinel():
    svc, session = _make_service()
    with pytest.raises(Exception) as exc_info:
        svc.update_settings({"openai_api_key": MASKED_SENTINEL})
    assert exc_info.value.status_code == 422


def test_reject_unknown_field():
    svc, session = _make_service()
    with pytest.raises(Exception) as exc_info:
        svc.update_settings({"nonexistent_field": "value"})
    assert exc_info.value.status_code == 422


def test_reject_path_traversal():
    svc, session = _make_service()
    with pytest.raises(Exception) as exc_info:
        svc.update_settings({"data_dir": "/tmp/../etc"})
    assert exc_info.value.status_code == 422


def test_schema_returns_field_metadata():
    svc, _ = _make_service()
    schema = svc.get_schema()
    assert "fields" in schema
    assert "model" in schema["fields"]
    assert schema["fields"]["openai_api_key"]["sensitive"] is True
    assert schema["fields"]["model"]["group"] == "llm"


def test_reset_group_removes_overrides():
    svc, session = _make_service()
    svc.update_settings({"model": "gpt-4", "request_timeout": "60"})
    session.commit()
    before = svc.get_effective_settings()
    assert before["model"] == "gpt-4"
    result = svc.reset_group("llm")
    session.commit()
    # After reset, model should revert to default (not "gpt-4")
    assert result["model"] != "gpt-4"
    assert result["request_timeout"] == "60"


def test_update_validates_against_model():
    svc, session = _make_service()
    with pytest.raises(Exception) as exc_info:
        svc.update_settings({"request_timeout": "not_a_number"})
    assert exc_info.value.status_code == 422


def test_absence_based_patch():
    svc, session = _make_service()
    svc.update_settings({"model": "gpt-4"})
    session.commit()
    result = svc.update_settings({"request_timeout": "60"})
    session.commit()
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

    # Only "model" in overrides; "request_timeout" is left as-is
    _sync_to_env({"model": "gpt-4o"}, env_path=env)

    text = env.read_text(encoding="utf-8")
    assert "COMPSYNTH_MODEL=gpt-4o" in text
    assert "COMPSYNTH_REQUEST_TIMEOUT=60" in text


def test_sync_to_env_removes_explicit_keys(tmp_path):
    env = tmp_path / ".env"
    env.write_text("COMPSYNTH_MODEL=gpt-4\nCOMPSYNTH_REQUEST_TIMEOUT=60\n", encoding="utf-8")

    from comp_synth.services.settings_service import _sync_to_env

    # Reset "model" → pass it in remove_keys
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

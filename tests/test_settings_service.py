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

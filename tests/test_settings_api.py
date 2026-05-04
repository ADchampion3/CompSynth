"""Settings API endpoint tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from comp_synth.api.app import create_app
from comp_synth.api.deps import get_session
from comp_synth.services.settings_service import MASKED_SENTINEL
from comp_synth.store.migrations import bootstrap_database


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    bootstrap_database(engine)
    return engine


@pytest.fixture()
def client():
    engine = _make_engine()
    app = create_app()

    def _test_session():
        session = sessionmaker(bind=engine)()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_session] = _test_session
    return TestClient(app)


def test_get_settings_returns_defaults(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "model" in data
    assert "request_timeout" in data


def test_get_settings_masks_sensitive(client):
    # First, set a real key value
    resp = client.patch("/api/settings", json={"openai_api_key": "sk-real-key-123"})
    assert resp.status_code == 200
    # Now GET should mask it
    resp = client.get("/api/settings")
    data = resp.json()
    assert data["openai_api_key"] == MASKED_SENTINEL


def test_patch_updates_value(client):
    resp = client.patch("/api/settings", json={"model": "gpt-4"})
    assert resp.status_code == 200
    assert resp.json()["model"] == "gpt-4"


def test_patch_rejects_masked_sentinel(client):
    resp = client.patch("/api/settings", json={"openai_api_key": MASKED_SENTINEL})
    assert resp.status_code == 422


def test_patch_rejects_unknown_field(client):
    resp = client.patch("/api/settings", json={"nonexistent": "value"})
    assert resp.status_code == 422


def test_patch_rejects_path_traversal(client):
    resp = client.patch("/api/settings", json={"data_dir": "/tmp/../etc/passwd"})
    assert resp.status_code == 422


def test_get_schema(client):
    resp = client.get("/api/settings/schema")
    assert resp.status_code == 200
    data = resp.json()
    assert "fields" in data
    assert "model" in data["fields"]
    assert data["fields"]["model"]["group"] == "llm"
    assert data["fields"]["openai_api_key"]["sensitive"] is True


def test_absence_based_patch(client):
    client.patch("/api/settings", json={"model": "gpt-4"})
    resp = client.patch("/api/settings", json={"request_timeout": "60"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "gpt-4"
    assert data["request_timeout"] == "60"
    # Restore
    client.patch("/api/settings", json={"model": "gpt-4o-mini", "request_timeout": "30"})


def test_patch_validates_types(client):
    resp = client.patch("/api/settings", json={"request_timeout": "not_a_number"})
    assert resp.status_code == 422

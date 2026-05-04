from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from comp_synth.store.migrations import bootstrap_database


def _make_repo():
    engine = create_engine("sqlite:///:memory:")
    bootstrap_database(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    from comp_synth.store.repositories.settings_repository import SettingsRepository
    return SettingsRepository(session), session


def test_load_returns_none_when_empty():
    repo, session = _make_repo()
    assert repo.load() is None


def test_save_and_load():
    repo, session = _make_repo()
    repo.save({"model": "gpt-4", "request_timeout": "60"})
    session.commit()
    loaded = repo.load()
    assert loaded == {"model": "gpt-4", "request_timeout": "60"}


def test_save_upserts():
    repo, session = _make_repo()
    repo.save({"model": "gpt-4"})
    session.commit()
    repo.save({"model": "gpt-3.5", "openai_api_key": "sk-test"})
    session.commit()
    loaded = repo.load()
    assert loaded["model"] == "gpt-3.5"
    assert loaded["openai_api_key"] == "sk-test"


def test_delete():
    repo, session = _make_repo()
    repo.save({"model": "gpt-4"})
    session.commit()
    repo.delete()
    session.commit()
    assert repo.load() is None

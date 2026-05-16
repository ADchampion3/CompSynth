"""Tests for DomainProxyRepository."""


from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from comp_synth.store.migrations import bootstrap_database
from comp_synth.store.repositories.domain_proxy_repository import (
    FAILURE_THRESHOLD,
    DomainProxyRepository,
)


def _make_repo() -> tuple[Session, DomainProxyRepository]:
    engine = create_engine("sqlite:///:memory:")
    bootstrap_database(engine)
    SessionFactory = sessionmaker(bind=engine)
    session = SessionFactory()
    return session, DomainProxyRepository(session)


def test_needs_proxy_returns_false_for_unknown_domain():
    session, repo = _make_repo()
    assert repo.needs_proxy("unknown.com") is False


def test_record_failure_increments_count():
    session, repo = _make_repo()
    repo.record_failure("example.com", "timeout")
    session.commit()

    assert repo.needs_proxy("example.com") is False
    entries = repo.list_all()
    assert len(entries) == 1
    assert entries[0].failure_count == 1
    assert entries[0].last_failure_error == "timeout"


def test_needs_proxy_set_after_threshold_failures():
    session, repo = _make_repo()

    for i in range(FAILURE_THRESHOLD - 1):
        repo.record_failure("blocked.com", f"timeout {i}")
        session.commit()

    assert repo.needs_proxy("blocked.com") is False

    repo.record_failure("blocked.com", "timeout final")
    session.commit()

    assert repo.needs_proxy("blocked.com") is True
    entries = repo.list_all()
    assert entries[0].failure_count == FAILURE_THRESHOLD
    assert entries[0].detected_at is not None


def test_record_success_resets_failure_count():
    session, repo = _make_repo()
    repo.record_failure("example.com", "timeout")
    repo.record_failure("example.com", "timeout")
    session.commit()
    assert repo.needs_proxy("example.com") is True

    repo.record_success("example.com")
    session.commit()

    entries = repo.list_all()
    assert entries[0].failure_count == 0
    assert repo.needs_proxy("example.com") is True


def test_record_success_noop_for_unknown_domain():
    session, repo = _make_repo()
    repo.record_success("unknown.com")
    session.commit()
    assert repo.list_all() == []


def test_clear_proxy_need():
    session, repo = _make_repo()
    repo.record_failure("blocked.com", "timeout")
    repo.record_failure("blocked.com", "timeout")
    session.commit()
    assert repo.needs_proxy("blocked.com") is True

    repo.clear_proxy_need("blocked.com")
    session.commit()

    assert repo.needs_proxy("blocked.com") is False
    entries = repo.list_all()
    assert entries[0].failure_count == 0


def test_failure_error_truncated_to_500():
    session, repo = _make_repo()
    long_error = "x" * 1000
    repo.record_failure("example.com", long_error)
    session.commit()

    entries = repo.list_all()
    assert len(entries[0].last_failure_error) == 500


def test_list_all_ordered_by_domain():
    session, repo = _make_repo()
    repo.record_failure("b.com", "err")
    repo.record_failure("a.com", "err")
    session.commit()

    entries = repo.list_all()
    assert [e.domain for e in entries] == ["a.com", "b.com"]

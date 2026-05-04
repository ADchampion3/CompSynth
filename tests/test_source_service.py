import pytest

from comp_synth.services.source_service import SourceService


def test_list_sources_reads_subscriptions_yaml(tmp_path):
    subscriptions = tmp_path / "subscriptions.yaml"
    subscriptions.write_text(
        """
sources:
  - type: rss
    url: https://example.test/feed.xml
    name: Example Feed
  - type: web
    url: https://example.test/
    selectors:
      - item_container: article
        url: a
    enabled: false
""",
        encoding="utf-8",
    )

    service = SourceService(subscriptions_path=subscriptions)

    sources = service.list_sources()

    assert [source.source_key for source in sources] == [
        "Example Feed",
        "https://example.test/",
    ]
    assert sources[0].enabled is True
    assert sources[1].enabled is False
    assert sources[1].selectors == [{"item_container": "article", "url": "a"}]


def test_list_sources_returns_empty_when_file_missing(tmp_path):
    service = SourceService(subscriptions_path=tmp_path / "missing.yaml")

    assert service.list_sources() == []


def test_list_sources_rejects_invalid_sources_shape(tmp_path):
    subscriptions = tmp_path / "subscriptions.yaml"
    subscriptions.write_text("sources: invalid\n", encoding="utf-8")

    service = SourceService(subscriptions_path=subscriptions)

    with pytest.raises(ValueError, match="sources"):
        service.list_sources()


def test_import_yaml_persists_sources_to_database(tmp_path):
    subscriptions = tmp_path / "subscriptions.yaml"
    subscriptions.write_text(
        """
sources:
  - type: rss
    url: https://example.test/feed.xml
    name: Example Feed
  - type: web
    url: https://example.test/
    selectors:
      - item_container: article
        url: a
    enabled: false
    priority: high
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "sources.db"

    service = SourceService(subscriptions_path=subscriptions, source_db_path=db_path)
    imported = service.import_yaml()

    assert [source.source_key for source in imported] == [
        "Example Feed",
        "https://example.test/",
    ]

    reloaded = SourceService(subscriptions_path=tmp_path / "missing.yaml", source_db_path=db_path)
    sources = reloaded.list_sources()

    assert [source.source_key for source in sources] == [
        "Example Feed",
        "https://example.test/",
    ]
    assert sources[0].source_type == "rss"
    assert sources[1].enabled is False
    assert sources[1].selectors == [{"item_container": "article", "url": "a"}]
    assert sources[1].raw_config["priority"] == "high"


def test_export_yaml_writes_database_sources(tmp_path):
    subscriptions = tmp_path / "subscriptions.yaml"
    subscriptions.write_text(
        """
sources:
  - type: rss
    url: https://example.test/feed.xml
    name: Example Feed
  - type: web
    url: https://example.test/
    selectors:
      - item_container: article
        url: a
    enabled: false
""",
        encoding="utf-8",
    )
    exported = tmp_path / "exported.yaml"
    service = SourceService(subscriptions_path=subscriptions, source_db_path=tmp_path / "sources.db")
    service.import_yaml()

    service.export_yaml(exported)

    reloaded = SourceService(subscriptions_path=exported)
    sources = reloaded.list_sources()
    assert [source.source_key for source in sources] == [
        "Example Feed",
        "https://example.test/",
    ]
    assert sources[1].enabled is False
    assert sources[1].selectors == [{"item_container": "article", "url": "a"}]


# --- Source CRUD ---


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "sources.db"


def test_create_source(db_path):
    service = SourceService(subscriptions_path=db_path.parent / "sub.yaml", source_db_path=db_path)
    source = service.create_source(source_type="rss", url="https://example.test/feed", name="Test")
    assert source.source_key == "Test"
    assert source.url == "https://example.test/feed"
    assert source.source_type == "rss"
    assert source.enabled is True

    sources = service.list_sources()
    assert len(sources) == 1
    assert sources[0].source_key == "Test"


def test_update_source(db_path):
    service = SourceService(subscriptions_path=db_path.parent / "sub.yaml", source_db_path=db_path)
    service.create_source(source_type="web", url="https://example.test/", name="Old")
    updated = service.update_source("Old", name="New", enabled=False)
    assert updated is not None
    assert updated.name == "New"
    assert updated.enabled is False


def test_update_source_not_found(db_path):
    service = SourceService(subscriptions_path=db_path.parent / "sub.yaml", source_db_path=db_path)
    result = service.update_source("nonexistent", name="New")
    assert result is None


def test_delete_source(db_path):
    service = SourceService(subscriptions_path=db_path.parent / "sub.yaml", source_db_path=db_path)
    service.create_source(source_type="web", url="https://example.test/", name="ToDelete")
    assert service.delete_source("ToDelete") is True
    assert service.list_sources() == []


def test_delete_source_not_found(db_path):
    service = SourceService(subscriptions_path=db_path.parent / "sub.yaml", source_db_path=db_path)
    assert service.delete_source("nonexistent") is False


def test_update_source_selectors(db_path):
    service = SourceService(subscriptions_path=db_path.parent / "sub.yaml", source_db_path=db_path)
    service.create_source(source_type="web", url="https://example.test/", name="SelTest")
    updated = service.update_source("SelTest", selectors=[{"item_container": "article", "url": "a", "title": "h2"}])
    assert updated is not None
    assert updated.selectors == [{"item_container": "article", "url": "a", "title": "h2"}]

    reloaded = service.list_sources()
    assert reloaded[0].selectors == [{"item_container": "article", "url": "a", "title": "h2"}]


def test_selectors_yaml_roundtrip(db_path):
    service = SourceService(subscriptions_path=db_path.parent / "sub.yaml", source_db_path=db_path)
    service.create_source(source_type="web", url="https://example.test/", name="Roundtrip")
    new_selectors = [{"item_container": "div.post", "url": "a.link", "title": "h2.title"}]
    service.update_source("Roundtrip", selectors=new_selectors)

    exported = db_path.parent / "exported.yaml"
    service.export_yaml(exported)

    reloaded_svc = SourceService(subscriptions_path=exported, source_db_path=db_path.parent / "reload.db")
    reloaded_svc.import_yaml()
    sources = reloaded_svc.list_sources()
    match = [s for s in sources if s.source_key == "Roundtrip"]
    assert len(match) == 1
    assert match[0].selectors == new_selectors

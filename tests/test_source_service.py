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
        "https://example.test/feed.xml",
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
        "https://example.test/feed.xml",
        "https://example.test/",
    ]

    reloaded = SourceService(subscriptions_path=tmp_path / "missing.yaml", source_db_path=db_path)
    sources = reloaded.list_sources()

    assert {source.source_key for source in sources} == {
        "https://example.test/feed.xml",
        "https://example.test/",
    }
    by_key = {s.source_key: s for s in sources}
    assert by_key["https://example.test/feed.xml"].source_type == "rss"
    assert by_key["https://example.test/"].enabled is False
    assert by_key["https://example.test/"].selectors == [{"item_container": "article", "url": "a"}]
    assert by_key["https://example.test/"].raw_config["priority"] == "high"


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
    assert {source.source_key for source in sources} == {
        "https://example.test/feed.xml",
        "https://example.test/",
    }
    by_key = {s.source_key: s for s in sources}
    assert by_key["https://example.test/"].enabled is False
    assert by_key["https://example.test/"].selectors == [{"item_container": "article", "url": "a"}]


# --- Source CRUD ---


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "sources.db"


def test_create_source(db_path):
    service = SourceService(subscriptions_path=db_path.parent / "sub.yaml", source_db_path=db_path)
    source = service.create_source(source_type="rss", url="https://example.test/feed", name="Test")
    assert source.source_key == "https://example.test/feed"
    assert source.url == "https://example.test/feed"
    assert source.source_type == "rss"
    assert source.enabled is True

    sources = service.list_sources()
    assert len(sources) == 1
    assert sources[0].source_key == "https://example.test/feed"


def test_update_source(db_path):
    service = SourceService(subscriptions_path=db_path.parent / "sub.yaml", source_db_path=db_path)
    service.create_source(source_type="web", url="https://example.test/", name="Old")
    updated = service.update_source("https://example.test/", name="New", enabled=False)
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
    assert service.delete_source("https://example.test/") is True
    assert service.list_sources() == []


def test_delete_source_not_found(db_path):
    service = SourceService(subscriptions_path=db_path.parent / "sub.yaml", source_db_path=db_path)
    assert service.delete_source("nonexistent") is False


def test_update_source_selectors(db_path):
    service = SourceService(subscriptions_path=db_path.parent / "sub.yaml", source_db_path=db_path)
    service.create_source(source_type="web", url="https://example.test/", name="SelTest")
    updated = service.update_source("https://example.test/", selectors=[{"item_container": "article", "url": "a", "title": "h2"}])
    assert updated is not None
    assert updated.selectors == [{"item_container": "article", "url": "a", "title": "h2"}]

    reloaded = service.list_sources()
    assert reloaded[0].selectors == [{"item_container": "article", "url": "a", "title": "h2"}]


def test_selectors_yaml_roundtrip(db_path):
    service = SourceService(subscriptions_path=db_path.parent / "sub.yaml", source_db_path=db_path)
    service.create_source(source_type="web", url="https://example.test/", name="Roundtrip")
    new_selectors = [{"item_container": "div.post", "url": "a.link", "title": "h2.title"}]
    service.update_source("https://example.test/", selectors=new_selectors)

    exported = db_path.parent / "exported.yaml"
    service.export_yaml(exported)

    reloaded_svc = SourceService(subscriptions_path=exported, source_db_path=db_path.parent / "reload.db")
    reloaded_svc.import_yaml()
    sources = reloaded_svc.list_sources()
    match = [s for s in sources if s.source_key == "https://example.test/"]
    assert len(match) == 1
    assert match[0].selectors == new_selectors


def test_import_yaml_full_overwrite_removes_extra_source(tmp_path):
    """YAML full overwrite: DB sources not in YAML are removed."""
    subscriptions = tmp_path / "subscriptions.yaml"
    subscriptions.write_text(
        """
sources:
  - type: rss
    url: https://keep.test/feed.xml
    name: KeepMe
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "sources.db"
    service = SourceService(subscriptions_path=subscriptions, source_db_path=db_path)

    # First import: creates the RSS source
    service.import_yaml()

    # Manually add an extra source not in YAML
    service.create_source(source_type="web", url="https://extra.test/", name="Extra")

    assert len(service.list_sources()) == 2

    # Re-import from YAML: should full overwrite, removing the extra source
    service.import_yaml()
    sources = service.list_sources()
    assert len(sources) == 1
    assert sources[0].source_key == "https://keep.test/feed.xml"


def test_import_yaml_name_change_no_duplicate(tmp_path):
    """Renaming a source via API then re-importing YAML should not create duplicates."""
    subscriptions = tmp_path / "subscriptions.yaml"
    subscriptions.write_text(
        """
sources:
  - type: web
    url: https://stable.test/
    name: Original
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "sources.db"
    service = SourceService(subscriptions_path=subscriptions, source_db_path=db_path)
    service.import_yaml()

    # Rename via API
    service.update_source("https://stable.test/", name="Renamed")

    # Re-import YAML (still has name: Original)
    service.import_yaml()
    sources = service.list_sources()
    assert len(sources) == 1
    assert sources[0].source_key == "https://stable.test/"
    assert sources[0].name == "Original"


def test_import_yaml_preserves_created_at(tmp_path):
    """Re-importing YAML should preserve created_at for existing sources."""
    subscriptions = tmp_path / "subscriptions.yaml"
    subscriptions.write_text(
        """
sources:
  - type: rss
    url: https://persist.test/feed.xml
    name: PersistCheck
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "sources.db"
    service = SourceService(subscriptions_path=subscriptions, source_db_path=db_path)
    service.import_yaml()

    # Read created_at directly from the underlying engine
    from sqlalchemy import text

    with service._engine.connect() as conn:
        original_created = conn.execute(
            text("SELECT created_at FROM sources WHERE source_key = :key"),
            {"key": "https://persist.test/feed.xml"},
        ).scalar_one()

    # Re-import same YAML
    service.import_yaml()

    with service._engine.connect() as conn:
        after_created = conn.execute(
            text("SELECT created_at FROM sources WHERE source_key = :key"),
            {"key": "https://persist.test/feed.xml"},
        ).scalar_one()

    assert after_created == original_created


def test_import_yaml_upsert_adds_new_source(tmp_path):
    """Adding a source to YAML and re-importing should insert it without removing existing."""
    subscriptions = tmp_path / "subscriptions.yaml"
    subscriptions.write_text(
        """
sources:
  - type: rss
    url: https://first.test/feed.xml
    name: First
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "sources.db"
    service = SourceService(subscriptions_path=subscriptions, source_db_path=db_path)
    service.import_yaml()
    assert len(service.list_sources()) == 1

    # Update YAML to add a second source
    subscriptions.write_text(
        """
sources:
  - type: rss
    url: https://first.test/feed.xml
    name: First
  - type: web
    url: https://second.test/
    name: Second
""",
        encoding="utf-8",
    )
    service.import_yaml()
    sources = service.list_sources()
    assert len(sources) == 2
    keys = {s.source_key for s in sources}
    assert keys == {"https://first.test/feed.xml", "https://second.test/"}


def test_update_selectors_then_export_writes_yaml(tmp_path):
    """Frontend updates selectors → export_yaml should write updated selectors to file."""
    import yaml

    subscriptions = tmp_path / "subscriptions.yaml"
    subscriptions.write_text(
        """
sources:
  - type: web
    url: https://example.test/
    name: TestSource
    selectors:
      - item_container: div.old
        url: a.old
        title: h2.old
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "sources.db"
    service = SourceService(subscriptions_path=subscriptions, source_db_path=db_path)
    service.import_yaml()

    # Simulate frontend: update selectors
    new_selectors = [{"item_container": "div.new", "url": "a.new"}]
    service.update_source("https://example.test/", selectors=new_selectors)

    # Simulate _sync_yaml: export to same path
    service.export_yaml()

    # Read YAML file and verify selectors changed
    with subscriptions.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    sources = data["sources"]
    assert len(sources) == 1
    assert sources[0]["selectors"] == new_selectors

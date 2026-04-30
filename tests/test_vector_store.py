from comp_synth.schema.content_item import ContentItem
from comp_synth.store.vector_store import VectorStore


def test_add_uses_idempotent_upsert_when_available():
    class Collection:
        def __init__(self):
            self.upserts = []

        def upsert(self, ids, documents):
            self.upserts.append((ids, documents))

    collection = Collection()
    store = VectorStore.__new__(VectorStore)
    store._collection = collection

    item = ContentItem(source="web", url="https://example.test/a", title="A")
    store.add([item])
    store.add([item])

    assert len(collection.upserts) == 2
    assert collection.upserts[0][0] == ["web:https://example.test/a"]

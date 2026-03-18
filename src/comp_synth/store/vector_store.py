from datetime import datetime, timedelta

import chromadb

from comp_synth.config import settings
from comp_synth.schemas.base import ContentItem


class VectorStore:
    """ChromaDB 向量存储封装，支持 TTL 过期清理"""

    def __init__(self, collection_name: str = "content_items"):
        self._client = chromadb.PersistentClient(
            path=str(settings.chroma_persist_dir)
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name
        )

    def add(self, items: list[ContentItem]) -> None:
        """添加内容项到向量存储"""
        if not items:
            return

        self._collection.add(
            ids=[item.id for item in items],
            documents=[item.content for item in items],
            metadatas=[
                {
                    "source": item.source,
                    "url": item.url,
                    "title": item.title,
                    "content_hash": item.content_hash,
                    "collected_at": item.collected_at.isoformat(),
                }
                for item in items
            ],
        )

    def search(self, query: str, k: int = 5) -> list[dict]:
        """语义搜索相关内容"""
        results = self._collection.query(query_texts=[query], n_results=k)
        return [
            {"document": doc, "metadata": meta}
            for doc, meta in zip(
                results["documents"][0], results["metadatas"][0]
            )
        ]

    def get_by_ids(self, ids: list[str]) -> list[dict]:
        """根据 source:url ID 列表批量获取内容"""
        if not ids:
            return []

        results = self._collection.get(ids=ids)
        return [
            {"id": id_, "document": doc, "metadata": meta}
            for id_, doc, meta in zip(
                results["ids"], results["documents"], results["metadatas"]
            )
        ]

    def cleanup_expired(self) -> None:
        """清理超过 TTL 的过期内容"""
        cutoff = (
            datetime.now() - timedelta(days=settings.vector_ttl_days)
        ).isoformat()

        expired = self._collection.get(
            where={"collected_at": {"$lt": cutoff}}
        )

        if expired["ids"]:
            self._collection.delete(ids=expired["ids"])

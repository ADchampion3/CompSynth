
import chromadb

from comp_synth.config import settings
from comp_synth.schemas.base import ContentItem


class VectorStore:
    """ChromaDB 向量存储封装，支持 TTL 过期清理"""

    def __init__(self, collection_name: str = "content_items"):
        # 确保数据目录存在
        settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(settings.chroma_persist_dir)
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name
        )

    def add(self, items: list[ContentItem]) -> None:
        """添加内容项到向量存储（仅存储ID和文档内容，metadata移至SQLite）"""
        if not items:
            return

        self._collection.add(
            ids=[item.id for item in items],
            documents=[item.content for item in items],
        )

    def search(self, query: str, k: int = 5) -> list[dict]:
        """语义搜索相关内容（metadata为空，元数据需从SQLite查询）"""
        results = self._collection.query(query_texts=[query], n_results=k)
        return [
            {"id": id_, "document": doc, "metadata": meta}
            for id_, doc, meta in zip(
                results["ids"][0], results["documents"][0], results["metadatas"][0]
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

    def cleanup_expired(self, expired_ids: list[str] | None = None) -> None:
        """清理过期内容（需要外部传入过期ID列表，元数据已移至SQLite）"""
        if expired_ids:
            self._collection.delete(ids=expired_ids)
        # 注: 过期ID应由 CrawlTracker 根据 SQLite 中的 crawled_at 计算后传入

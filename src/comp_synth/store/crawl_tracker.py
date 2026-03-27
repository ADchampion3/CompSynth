import json
import sqlite3
from datetime import datetime, timedelta, timezone

from comp_synth.config import settings


class CrawlTracker:
    """爬取状态追踪，基于 SQLite 实现去重和状态管理"""

    def __init__(self):
        self._db_path = str(settings.crawl_db_path)
        # 确保数据目录存在
        settings.crawl_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    article_id TEXT PRIMARY KEY,      -- e.g., "web:https://example.com/article"
                    vector_id TEXT NOT NULL,            -- ChromaDB ID (同article_id)
                    crawled_at TIMESTAMP NOT NULL,
                    published_at TIMESTAMP,
                    content TEXT DEFAULT '',
                    summary TEXT DEFAULT '',
                    title TEXT DEFAULT '',
                    url TEXT NOT NULL,
                    source TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    liked INTEGER DEFAULT 0
                )
            """)
            # 兼容已有数据库：尝试添加新列
            for col, default in [
                ("summary", "''"),
                ("title", "''"),
                ("vector_id", "article_id"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE articles ADD COLUMN {col} TEXT DEFAULT {default}")
                except sqlite3.OperationalError:
                    pass  # 列已存在
            try:
                conn.execute("ALTER TABLE articles ADD COLUMN liked INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            # 旧版本拼写错误迁移：pulished_at -> published_at
            try:
                conn.execute("ALTER TABLE articles ADD COLUMN published_at TIMESTAMP")
                # 如果旧表有 pulished_at 列，迁移数据
                try:
                    rows = conn.execute("SELECT article_id, pulished_at FROM articles WHERE pulished_at IS NOT NULL AND pulished_at != ''").fetchall()
                    for article_id, pulished_at in rows:
                        conn.execute("UPDATE articles SET published_at = ? WHERE article_id = ?", (pulished_at, article_id))
                except sqlite3.OperationalError:
                    pass  # pulished_at 列不存在，无需迁移
            except sqlite3.OperationalError:
                pass  # published_at 列已存在

    def is_crawled(self, source: str, url: str) -> bool:
        """检查 URL 是否已被爬取"""
        article_id = f"{source}:{url}"
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM articles WHERE article_id = ?",
                (article_id,),
            ).fetchone()
            return row is not None

    def get_last_crawl_time(self, source: str, feed_url: str) -> datetime | None:
        """获取指定来源和 feed 的最近爬取时间"""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """SELECT MAX(crawled_at) FROM articles
                   WHERE source = ? AND json_extract(metadata, '$.feed_url') = ?""",
                (source, feed_url),
            ).fetchone()
            if row and row[0]:
                dt = datetime.fromisoformat(row[0])
                return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
            return None

    def get_today_items(self, source: str) -> list[dict]:
        """获取今天爬取过的所有 items"""
        today = datetime.now(timezone.utc).date().isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT article_id, source, url, crawled_at, summary, title, metadata, content FROM articles
                   WHERE source = ? AND crawled_at LIKE ?""",
                (source, f"{today}%"),
            ).fetchall()
            return [dict(row) for row in rows]

    def save_article(
        self,
        article_id: str,
        title: str,
        summary: str,
        content: str = "",
        metadata: dict | None = None,
        published_at: str | None = None,
    ) -> None:
        """保存文章元数据到 SQLite（向量数据已移至 ChromaDB）"""
        source, url = article_id.split(":", 1) if ":" in article_id else ("unknown", article_id)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO articles
                   (article_id, vector_id, crawled_at, published_at, content, summary, title, url, source, metadata, liked)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    article_id,
                    article_id,  # vector_id
                    datetime.now(timezone.utc).isoformat(),
                    published_at,
                    content,
                    summary,
                    title,
                    url,
                    source,
                    json.dumps(metadata or {}),
                    0,  # liked
                ),
            )

    def save_articles(self, items: list[dict]) -> None:
        """批量保存文章元数据到 SQLite（单连接单事务）"""
        if not items:
            return
        records = []
        for item in items:
            article_id = item["article_id"]
            source, url = article_id.split(":", 1) if ":" in article_id else ("unknown", article_id)
            records.append((
                article_id,
                article_id,
                datetime.now(timezone.utc).isoformat(),
                item.get("published_at"),
                item.get("content", ""),
                item.get("summary", ""),
                item.get("title", ""),
                url,
                source,
                json.dumps(item.get("metadata") or {}),
                0,
            ))
        with sqlite3.connect(self._db_path) as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO articles
                   (article_id, vector_id, crawled_at, published_at, content, summary, title, url, source, metadata, liked)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                records,
            )

    def get_article_by_id(self, article_id: str) -> dict | None:
        """根据 article_id 获取文章元数据"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM articles WHERE article_id = ?",
                (article_id,),
            ).fetchone()
            if row:
                return dict(row)
            return None

    def get_articles_by_ids(self, article_ids: list[str]) -> list[dict]:
        """根据 article_id 列表批量获取文章元数据"""
        if not article_ids:
            return []
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            placeholders = ",".join("?" * len(article_ids))
            rows = conn.execute(
                f"SELECT * FROM articles WHERE article_id IN ({placeholders})",
                article_ids,
            ).fetchall()
            return [dict(row) for row in rows]

    def get_expired_article_ids(self, ttl_days: int = 30) -> list[str]:
        """获取超过 TTL 的文章 ID（用于清理向量库）"""
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=ttl_days)
        ).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT article_id FROM articles WHERE crawled_at < ?",
                (cutoff,),
            ).fetchall()
            return [row["article_id"] for row in rows]

    def set_liked(self, source: str, url: str, liked: bool = True) -> None:
        """设置/取消内容的 like 状态"""
        article_id = f"{source}:{url}"
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE articles SET liked = ? WHERE article_id = ?",
                (1 if liked else 0, article_id),
            )

    def get_liked_items(self) -> list[dict]:
        """查询所有 liked 的记录"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT article_id, source, url, crawled_at, summary, title, content,metadata FROM articles WHERE liked = 1"
            ).fetchall()
            return [dict(row) for row in rows]

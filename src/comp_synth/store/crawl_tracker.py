import json
import sqlite3
from datetime import datetime

from comp_synth.config import settings


class CrawlTracker:
    """爬取状态追踪，基于 SQLite 实现去重和状态管理"""

    def __init__(self):
        self._db_path = str(settings.crawl_db_path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS crawl_records (
                    source TEXT NOT NULL,
                    url TEXT NOT NULL,
                    crawled_at TEXT NOT NULL,
                    status TEXT DEFAULT 'success',
                    metadata TEXT DEFAULT '{}',
                    liked INTEGER DEFAULT 0,
                    PRIMARY KEY (source, url)
                )
            """)
            # 兼容已有数据库：尝试添加 liked 列
            try:
                conn.execute("ALTER TABLE crawl_records ADD COLUMN liked INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # 列已存在

    def is_crawled(self, source: str, url: str) -> bool:
        """检查 URL 是否已被爬取"""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM crawl_records WHERE source = ? AND url = ?",
                (source, url),
            ).fetchone()
            return row is not None

    def get_last_crawl_time(self, source: str, feed_url: str) -> datetime | None:
        """获取指定来源和 feed 的最近爬取时间"""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """SELECT MAX(crawled_at) FROM crawl_records
                   WHERE source = ? AND json_extract(metadata, '$.feed_url') = ?""",
                (source, feed_url),
            ).fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0])
            return None

    def mark_crawled(
        self, source: str, url: str, status: str = "success", metadata: dict | None = None
    ) -> None:
        """标记 URL 为已爬取"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO crawl_records
                   (source, url, crawled_at, status, metadata)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    source,
                    url,
                    datetime.now().isoformat(),
                    status,
                    json.dumps(metadata or {}),
                ),
            )

    def set_liked(self, source: str, url: str, liked: bool = True) -> None:
        """设置/取消内容的 like 状态"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE crawl_records SET liked = ? WHERE source = ? AND url = ?",
                (1 if liked else 0, source, url),
            )

    def get_liked_items(self) -> list[dict]:
        """查询所有 liked 的记录"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT source, url, crawled_at, status, metadata FROM crawl_records WHERE liked = 1"
            ).fetchall()
            return [
                {
                    "source": row["source"],
                    "url": row["url"],
                    "crawled_at": row["crawled_at"],
                    "status": row["status"],
                    "metadata": json.loads(row["metadata"]),
                }
                for row in rows
            ]

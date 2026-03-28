import json
import sqlite3
from datetime import datetime, timedelta

from comp_synth.config import settings
from comp_synth.schema.site_chema import SiteSchema


class SchemaStore:
    """站点 Schema 持久化存储，基于 SQLite 实现"""

    def __init__(self):
        self._db_path = str(settings.site_schema_db_path)
        # 确保数据目录存在
        settings.site_schema_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS site_schemas (
                    site_name TEXT PRIMARY KEY,
                    site_url TEXT NOT NULL,
                    selectors TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_llm_call TEXT,
                    list_selectors TEXT DEFAULT '{}'
                )
            """)
            try:
                conn.execute("ALTER TABLE site_schemas ADD COLUMN list_selectors TEXT DEFAULT '{}'")
            except sqlite3.OperationalError:
                pass  # 列已存在

    def get(self, site_name: str) -> SiteSchema | None:
        """根据站点名获取 Schema"""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM site_schemas WHERE site_name = ?",
                (site_name,),
            ).fetchone()
            if row is None:
                return None
            selectors = json.loads(row[2])
            # 向后兼容：旧的 dict 格式迁移为 list[dict] 格式
            if isinstance(selectors, dict):
                selectors = [selectors]
            return SiteSchema(
                site_name=row[0],
                site_url=row[1],
                selectors=selectors,
                created_at=datetime.fromisoformat(row[3]),
                updated_at=datetime.fromisoformat(row[4]),
                last_llm_call=datetime.fromisoformat(row[5]) if row[5] else None,
            )

    def save(self, schema: SiteSchema) -> None:
        """保存或更新 Schema，created_at 仅在首次创建时设置"""
        with sqlite3.connect(self._db_path) as conn:
            existing = conn.execute(
                "SELECT created_at, selectors FROM site_schemas WHERE site_name = ?",
                (schema.site_name,),
            ).fetchone()

            if existing:
                # UPDATE - 保留 created_at 和已有的 list_selectors（避免覆盖）
                conn.execute(
                    """UPDATE site_schemas
                       SET site_url = ?, selectors = ?, updated_at = ?, last_llm_call = ?
                       WHERE site_name = ?""",
                    (
                        schema.site_url,
                        json.dumps(schema.selectors),
                        datetime.now().isoformat(),
                        schema.last_llm_call.isoformat() if schema.last_llm_call else None,
                        schema.site_name,
                    ),
                )
            else:
                # INSERT
                conn.execute(
                    """INSERT INTO site_schemas
                       (site_name, site_url, selectors, created_at, updated_at, last_llm_call)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        schema.site_name,
                        schema.site_url,
                        json.dumps(schema.selectors),
                        datetime.now().isoformat(),
                        datetime.now().isoformat(),
                        schema.last_llm_call.isoformat() if schema.last_llm_call else None,
                    ),
                )

    def can_use_llm(self, site_name: str) -> bool:
        """检查是否可以对该站点调用 LLM（每站每天 1 次）"""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT last_llm_call FROM site_schemas WHERE site_name = ?",
                (site_name,),
            ).fetchone()

            if row is None or row[0] is None:
                return True
            last_call = datetime.fromisoformat(row[0])
            return (datetime.now() - last_call) > timedelta(hours=24)

    def update_selectors(self, site_name: str, selectors: list[dict[str, str]]) -> None:
        """更新指定站点的 selectors"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """UPDATE site_schemas
                   SET selectors = ?, updated_at = ?
                   WHERE site_name = ?""",
                (json.dumps(selectors), datetime.now().isoformat(), site_name),
            )

    def mark_llm_called(self, site_name: str) -> None:
        """标记该站点已调用 LLM（直接 UPDATE）"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """UPDATE site_schemas
                   SET last_llm_call = ?, updated_at = ?
                   WHERE site_name = ?""",
                (datetime.now().isoformat(), datetime.now().isoformat(), site_name),
            )

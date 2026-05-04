"""Repository for persisted settings overrides (single-row JSON blob)."""

import json

from sqlalchemy import text
from sqlalchemy.orm import Session


class SettingsRepository:
    """Data access for the settings JSON blob."""

    def __init__(self, session: Session):
        self._session = session

    def load(self) -> dict[str, str] | None:
        row = self._session.execute(
            text("SELECT data FROM settings WHERE id = 1")
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def save(self, data: dict[str, str]) -> None:
        blob = json.dumps(data, ensure_ascii=False)
        existing = self._session.execute(
            text("SELECT id FROM settings WHERE id = 1")
        ).fetchone()
        if existing:
            self._session.execute(
                text("UPDATE settings SET data = :data, updated_at = datetime('now') WHERE id = 1"),
                {"data": blob},
            )
        else:
            self._session.execute(
                text("INSERT INTO settings (id, data) VALUES (1, :data)"),
                {"data": blob},
            )

    def delete(self) -> None:
        self._session.execute(text("DELETE FROM settings WHERE id = 1"))

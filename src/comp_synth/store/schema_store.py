"""Schema store - site CSS selector schema persistence via SQLite."""

from sqlalchemy.orm import sessionmaker

from comp_synth.config import settings
from comp_synth.schema.site_chema import SiteSchema
from comp_synth.store.migrations import bootstrap_database
from comp_synth.store.models import resolve_db_path
from comp_synth.store.repositories.site_schema_repository import SiteSchemaRepository


class SchemaStore:
    """Site CSS selector schema storage using SQLite + SQLAlchemy."""

    def __init__(self):
        self._db_path = resolve_db_path(settings.site_schema_db_path, "site_schemas.db")
        # Ensure data directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = None
        self._session_factory = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database connection and create tables."""
        from sqlalchemy import create_engine

        self._engine = create_engine(f"sqlite:///{self._db_path}", echo=False)
        bootstrap_database(self._engine)
        self._ensure_schema_columns()
        self._session_factory = sessionmaker(bind=self._engine)

    def _ensure_schema_columns(self) -> None:
        """Add nullable selector-refresh columns for existing SQLite databases."""
        from sqlalchemy import inspect, text

        inspector = inspect(self._engine)
        if not inspector.has_table("site_schemas"):
            return

        columns = {column["name"] for column in inspector.get_columns("site_schemas")}
        statements = []
        if "last_stale_refresh_call" not in columns:
            statements.append("ALTER TABLE site_schemas ADD COLUMN last_stale_refresh_call DATETIME")
        if "stale_refresh_count" not in columns:
            statements.append("ALTER TABLE site_schemas ADD COLUMN stale_refresh_count INTEGER DEFAULT 0")

        if statements:
            with self._engine.begin() as conn:
                for statement in statements:
                    conn.execute(text(statement))

    def _with_session(self, fn):
        """Execute a function within a session context."""
        with self._session_factory() as session:
            result = fn(SiteSchemaRepository(session))
            session.commit()
            return result

    def get(self, site_name: str) -> SiteSchema | None:
        """Get site schema by site name."""
        return self._with_session(lambda repo: repo.get(site_name))

    def save(self, schema: SiteSchema) -> None:
        """Save or update site schema."""
        self._with_session(lambda repo: repo.save(schema))

    def can_use_llm(self, site_name: str) -> bool:
        """Check if LLM can be called for this site (rate limit: once per 24 hours)."""
        return self._with_session(lambda repo: repo.can_use_llm(site_name))

    def update_selectors(self, site_name: str, selectors: list[dict[str, str]]) -> None:
        """Update the selectors for a site."""
        self._with_session(lambda repo: repo.update_selectors(site_name, selectors))

    def mark_llm_called(self, site_name: str) -> None:
        """Mark that LLM was called for this site."""
        self._with_session(lambda repo: repo.mark_llm_called(site_name))

    def can_refresh_stale_selectors(self, site_name: str) -> bool:
        """Check if stale selector refresh can call the LLM for this site."""
        from comp_synth.config import settings

        return self._with_session(
            lambda repo: repo.can_refresh_stale_selectors(
                site_name,
                settings.selector_zero_refresh_cooldown_hours,
            )
        )

    def mark_stale_refresh_called(self, site_name: str) -> None:
        """Mark that stale selector refresh was attempted for this site."""
        self._with_session(lambda repo: repo.mark_stale_refresh_called(site_name))

"""Schema store - site CSS selector schema persistence via SQLite."""

from sqlalchemy.orm import sessionmaker

from comp_synth.config import settings
from comp_synth.schema.site_chema import SiteSchema
from comp_synth.store.models import Base, resolve_db_path
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
        Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(bind=self._engine)

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

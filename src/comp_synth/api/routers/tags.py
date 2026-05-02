"""Tags API router with in-process cache."""

import time

from fastapi import APIRouter, Depends

from comp_synth.api.deps import get_article_service
from comp_synth.api.schemas import TagVocabularyResponse
from comp_synth.services.article_service import ArticleService

router = APIRouter(tags=["tags"])

_CACHE_TTL = 60
_cache: list[str] | None = None
_cache_ts: float = 0


def invalidate_tag_cache() -> None:
    global _cache, _cache_ts
    _cache = None
    _cache_ts = 0


@router.get("/tags", response_model=TagVocabularyResponse)
def get_tags(service: ArticleService = Depends(get_article_service)):
    global _cache, _cache_ts
    now = time.monotonic()
    if _cache is not None and (now - _cache_ts) < _CACHE_TTL:
        return TagVocabularyResponse(tags=_cache)
    _cache = service.get_tag_vocabulary()
    _cache_ts = now
    return TagVocabularyResponse(tags=_cache)

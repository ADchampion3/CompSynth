"""Articles API router."""

from fastapi import APIRouter, Depends, HTTPException, Query

from comp_synth.api.deps import get_article_service
from comp_synth.api.mappers import content_item_to_response
from comp_synth.api.routers.tags import invalidate_tag_cache
from comp_synth.api.schemas import (
    ArticleLikeUpdate,
    ArticleNoteUpdate,
    ArticlePageResponse,
    ArticleResponse,
    ArticleStateResponse,
    ArticleStateUpdate,
    ErrorDetail,
    InboxSourceResponse,
    TagsUpdateRequest,
)
from comp_synth.services.article_service import ArticleService

router = APIRouter(tags=["articles"])


@router.get("/articles/sources", response_model=list[InboxSourceResponse])
def list_inbox_sources(
    service: ArticleService = Depends(get_article_service),
):
    sources = service.list_inbox_sources()
    return [InboxSourceResponse(source=s, article_count=c) for s, c in sources]


@router.get("/articles", response_model=ArticlePageResponse)
def list_articles(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source: str | None = None,
    tag: str | None = None,
    liked: bool | None = None,
    query: str | None = None,
    read_state: str | None = None,
    service: ArticleService = Depends(get_article_service),
):
    page = service.list_articles(
        limit=limit, offset=offset, source=source, tag=tag,
        liked=liked, query=query, read_state=read_state,
    )
    article_ids = [item.id for item in page.items]
    states = service.batch_get_read_states(article_ids)
    return ArticlePageResponse(
        items=[content_item_to_response(item, read_state=states.get(item.id, "unread")) for item in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/articles/detail", response_model=ArticleResponse)
def get_article(
    article_id: str = Query(..., description="Article ID (source:url)"),
    service: ArticleService = Depends(get_article_service),
):
    article = service.get_article(article_id)
    if article is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorDetail(
                problem="Article not found",
                cause="No article with that id",
                fix="List articles to find valid ids.",
            ).model_dump(),
        )
    return content_item_to_response(article)


@router.get("/articles/state", response_model=ArticleStateResponse)
def get_article_state(
    article_id: str = Query(..., description="Article ID"),
    service: ArticleService = Depends(get_article_service),
):
    state = service.get_article_state(article_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorDetail(
                problem="Article state not found",
                cause="No article with that id",
                fix="List articles to find valid ids.",
            ).model_dump(),
        )
    return ArticleStateResponse(
        article_id=state.article_id,
        read_state=state.read_state,
        user_note=state.user_note,
        last_viewed_at=state.last_viewed_at,
        created_at=state.created_at,
        updated_at=state.updated_at,
    )


@router.patch("/articles/state", response_model=ArticleStateResponse)
def update_article_state(
    body: ArticleStateUpdate,
    article_id: str = Query(..., description="Article ID"),
    service: ArticleService = Depends(get_article_service),
):
    ok = service.set_read_state(article_id, body.read_state)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=ErrorDetail(
                problem="Article not found",
                cause="No article with that id",
                fix="List articles to find valid ids.",
            ).model_dump(),
        )
    state = service.get_article_state(article_id)
    if state is None:
        raise HTTPException(status_code=500, detail="Failed to read article state after update")
    return ArticleStateResponse(
        article_id=state.article_id,
        read_state=state.read_state,
        user_note=state.user_note,
        last_viewed_at=state.last_viewed_at,
        created_at=state.created_at,
        updated_at=state.updated_at,
    )


@router.patch("/articles/like", response_model=ArticleResponse)
def update_article_like(
    body: ArticleLikeUpdate,
    article_id: str = Query(..., description="Article ID"),
    service: ArticleService = Depends(get_article_service),
):
    article = service.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    service.set_liked(article_id, body.liked)
    updated = service.get_article(article_id)
    return content_item_to_response(updated)


@router.patch("/articles/note", response_model=ArticleStateResponse)
def update_article_note(
    body: ArticleNoteUpdate,
    article_id: str = Query(..., description="Article ID"),
    service: ArticleService = Depends(get_article_service),
):
    ok = service.save_note(article_id, body.user_note)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=ErrorDetail(
                problem="Article not found",
                cause="No article with that id",
                fix="List articles to find valid ids.",
            ).model_dump(),
        )
    state = service.get_article_state(article_id)
    if state is None:
        raise HTTPException(status_code=500, detail="Failed to read article state after update")
    return ArticleStateResponse(
        article_id=state.article_id,
        read_state=state.read_state,
        user_note=state.user_note,
        last_viewed_at=state.last_viewed_at,
        created_at=state.created_at,
        updated_at=state.updated_at,
    )


@router.patch("/articles/tags", response_model=ArticleResponse)
def update_article_tags(
    body: TagsUpdateRequest,
    article_id: str = Query(..., description="Article ID"),
    service: ArticleService = Depends(get_article_service),
):
    article = service.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    service.update_tags(article_id, body.tags)
    invalidate_tag_cache()
    updated = service.get_article(article_id)
    return content_item_to_response(updated)

"""Wiki API router — Second Brain CRUD, ingest, query, lint, graph."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.agent.dependencies import AgentTenantContext
from app.modules.auth.dependencies import CurrentUser
from app.modules.wiki.schemas import (
    WikiBulkDeleteResponse,
    WikiGraphResponse,
    WikiIngestRequest,
    WikiIngestResponse,
    WikiLintResponse,
    WikiPageCreate,
    WikiPageDetailResponse,
    WikiPageListResponse,
    WikiPageResponse,
    WikiPageUpdate,
)
from app.modules.wiki.services.wiki_service import ImmutablePageError, WikiService

router = APIRouter(prefix="/wiki", tags=["wiki"])


def _get_wiki_service(db: Annotated[AsyncSession, Depends(get_db)]) -> WikiService:
    return WikiService(db)


@router.get("/pages", response_model=WikiPageListResponse)
async def list_pages(
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[WikiService, Depends(_get_wiki_service)],
    folder: str | None = Query(default=None),
    page_status: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> WikiPageListResponse:
    _ = current_user
    pages, total = await service.list_pages(
        tenant_ctx=tenant_ctx,
        folder=folder,
        status=page_status,
        q=q,
        limit=limit,
        offset=offset,
    )
    return WikiPageListResponse(pages=pages, total=total)


@router.get("/pages/{page_id}", response_model=WikiPageDetailResponse)
async def get_page(
    page_id: str,
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[WikiService, Depends(_get_wiki_service)],
) -> WikiPageDetailResponse:
    _ = current_user
    detail = await service.get_page(tenant_ctx=tenant_ctx, page_id=page_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    return detail


@router.post("/pages", status_code=status.HTTP_201_CREATED, response_model=WikiPageResponse)
async def create_page(
    payload: WikiPageCreate,
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[WikiService, Depends(_get_wiki_service)],
) -> WikiPageResponse:
    _ = current_user
    return await service.create_page(
        tenant_ctx=tenant_ctx,
        folder=payload.folder,
        slug=payload.slug,
        title=payload.title,
        body_md=payload.body_md,
        frontmatter=payload.frontmatter,
        source_url=payload.source_url,
    )


@router.patch("/pages/{page_id}", response_model=WikiPageResponse)
async def update_page(
    page_id: str,
    payload: WikiPageUpdate,
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[WikiService, Depends(_get_wiki_service)],
) -> WikiPageResponse:
    _ = current_user
    update_kwargs: dict = {
        "tenant_ctx": tenant_ctx,
        "page_id": page_id,
        "title": payload.title,
        "body_md": payload.body_md,
        "status": payload.status,
    }
    if "frontmatter" in payload.model_fields_set:
        update_kwargs["frontmatter"] = payload.frontmatter
    try:
        result = await service.update_page(**update_kwargs)
    except ImmutablePageError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot modify an immutable (raw) page",
        ) from err
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    return result


@router.delete("/pages", response_model=WikiBulkDeleteResponse)
async def bulk_delete_pages(
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[WikiService, Depends(_get_wiki_service)],
    folder: str | None = Query(default=None),
    page_status: str | None = Query(default=None, alias="status"),
    page_ids: list[str] | None = Query(default=None),
    force: bool = Query(default=False),
) -> WikiBulkDeleteResponse:
    _ = current_user
    deleted = await service.bulk_delete(
        tenant_ctx=tenant_ctx,
        folder=folder,
        status=page_status,
        page_ids=page_ids if page_ids else None,
        force=force,
    )
    return WikiBulkDeleteResponse(deleted=deleted)


@router.post("/purge", response_model=WikiBulkDeleteResponse)
async def purge_all_pages(
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[WikiService, Depends(_get_wiki_service)],
    x_confirm: str | None = Header(default=None, alias="X-Confirm"),
) -> WikiBulkDeleteResponse:
    _ = current_user
    if x_confirm != "purge":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or invalid X-Confirm: purge header",
        )
    deleted = await service.purge_all(tenant_ctx=tenant_ctx)
    return WikiBulkDeleteResponse(deleted=deleted)


@router.delete("/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_page(
    page_id: str,
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[WikiService, Depends(_get_wiki_service)],
) -> None:
    _ = current_user
    try:
        deleted = await service.delete_page(tenant_ctx=tenant_ctx, page_id=page_id)
    except ImmutablePageError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete an immutable (raw) page",
        ) from err
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")


@router.post("/pages/{page_id}/deprecate", response_model=WikiPageResponse)
async def deprecate_page(
    page_id: str,
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[WikiService, Depends(_get_wiki_service)],
) -> WikiPageResponse:
    _ = current_user
    result = await service.deprecate_page(tenant_ctx=tenant_ctx, page_id=page_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    return result


@router.post("/ingest", response_model=WikiIngestResponse)
async def ingest(
    payload: WikiIngestRequest,
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[WikiService, Depends(_get_wiki_service)],
) -> WikiIngestResponse:
    _ = current_user
    return await service.ingest(
        tenant_ctx=tenant_ctx,
        content=payload.content,
        source_url=payload.source_url,
        title=payload.title,
    )


@router.get("/graph", response_model=WikiGraphResponse)
async def get_graph(
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[WikiService, Depends(_get_wiki_service)],
    folder: str | None = Query(default=None),
) -> WikiGraphResponse:
    _ = current_user
    return await service.get_graph(tenant_ctx=tenant_ctx, folder=folder)


@router.post("/lint", response_model=WikiLintResponse)
async def lint(
    current_user: CurrentUser,
    tenant_ctx: AgentTenantContext,
    service: Annotated[WikiService, Depends(_get_wiki_service)],
) -> WikiLintResponse:
    _ = current_user
    return await service.lint(tenant_ctx=tenant_ctx)

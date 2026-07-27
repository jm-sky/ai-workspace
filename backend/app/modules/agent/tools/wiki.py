"""Wiki librarian tools for the agent loop: ingest, query, lint."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.tools.base import AgentTool, AgentToolDefinition
from app.modules.tenants.service import TenantContext
from app.modules.wiki.services.wiki_service import WikiService


class WikiIngestTool(AgentTool):
    """Ingest source content into the wiki (Raw → Summary → Entities/Concepts → Log)."""

    def __init__(self, *, tenant_ctx: TenantContext, db: AsyncSession):
        self.tenant_ctx = tenant_ctx
        self.wiki_service = WikiService(db)

    @property
    def definition(self) -> AgentToolDefinition:
        return AgentToolDefinition(
            name="wiki_ingest",
            description=(
                "Ingest source content (article, doc, notes) into the Second Brain wiki. "
                "Creates an immutable Raw page, a Summary, and rippled Entity/Concept pages. "
                "Use for substantial source material — for short facts, use memory_save instead."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Full text content to ingest",
                    },
                    "source_url": {
                        "type": "string",
                        "description": "Optional URL of the source",
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional title for the ingested content",
                    },
                },
                "required": ["content"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        content = str(arguments.get("content", "")).strip()
        if not content:
            return {"error": "content is required"}

        source_url = arguments.get("source_url")
        title = arguments.get("title")

        result = await self.wiki_service.ingest(
            tenant_ctx=self.tenant_ctx,
            content=content,
            source_url=source_url,
            title=title,
        )
        return {
            "rawPageId": result.rawPageId,
            "summaryPageId": result.summaryPageId,
            "rippledPages": result.rippledPages,
            "truncated": result.truncated,
        }


class WikiQueryTool(AgentTool):
    """Search the wiki knowledge base (source_type=wiki only)."""

    def __init__(self, *, tenant_ctx: TenantContext, db: AsyncSession):
        self.tenant_ctx = tenant_ctx
        self.wiki_service = WikiService(db)

    @property
    def definition(self) -> AgentToolDefinition:
        return AgentToolDefinition(
            name="wiki_query",
            description=(
                "Search the user's Second Brain wiki for relevant material. "
                "Returns quotes with page slug for citation. "
                "Use for questions about ingested materials — for personal facts, use memory_search."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default 8)",
                    },
                },
                "required": ["query"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = str(arguments.get("query", "")).strip()
        if not query:
            return {"error": "query is required"}

        limit = int(arguments.get("limit") or 8)
        results = await self.wiki_service.query(
            tenant_ctx=self.tenant_ctx,
            query=query,
            limit=min(limit, 50),
        )
        return {
            "total": len(results),
            "results": results,
        }


class WikiLintTool(AgentTool):
    """Lint the wiki: report dangling links, orphans, pages without links."""

    def __init__(self, *, tenant_ctx: TenantContext, db: AsyncSession):
        self.tenant_ctx = tenant_ctx
        self.wiki_service = WikiService(db)

    @property
    def definition(self) -> AgentToolDefinition:
        return AgentToolDefinition(
            name="wiki_lint",
            description=(
                "Lint the Second Brain wiki: reports dangling links, orphan pages, "
                "and pages without outgoing links. Applies mechanical fixes (link rebuild) "
                "automatically. Does NOT auto-deprecate — requires user confirmation."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "enum": ["all", "folder"],
                        "description": "Scope of lint check (default all)",
                    },
                },
                "required": [],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        result = await self.wiki_service.lint(tenant_ctx=self.tenant_ctx)
        return {
            "issues": [
                {
                    "type": issue.type,
                    "pageId": issue.pageId,
                    "slug": issue.slug,
                    "detail": issue.detail,
                }
                for issue in result.issues
            ],
            "fixesApplied": result.fixesApplied,
        }

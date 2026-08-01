"""RAG maintenance CLI commands."""

import asyncio

import typer
from rich.console import Console

from ..main import COMMAND_GROUPS, show_group_interactive_menu

rag_app = typer.Typer(
    name="rag",
    help="Document RAG maintenance commands",
    no_args_is_help=False,
)

console = Console()


@rag_app.callback(invoke_without_command=True)
def rag_callback(ctx: typer.Context) -> None:
    """Show interactive menu when no subcommand is provided."""
    if ctx.invoked_subcommand is None:
        show_group_interactive_menu("rag", COMMAND_GROUPS["rag"])


@rag_app.command("reembed")
def reembed(
    batch: int = typer.Option(100, "--batch", help="Chunks embedded per API batch/commit"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Report how many chunks need re-embedding, without writing"),
) -> None:
    """Re-embed document_chunks whose embedding_version is behind AI_EMBEDDING_VERSION.

    Resumable (filters by embedding_version) and idempotent (a second run
    once caught up processes 0 rows).

    Examples:
        python -m cli rag reembed --dry-run
        python -m cli rag reembed --batch 50
    """
    asyncio.run(_reembed_async(batch=batch, dry_run=dry_run))


@rag_app.command("reindex-wiki")
def reindex_wiki(
    tenant_id: str | None = typer.Option(None, "--tenant-id", help="Limit to one tenant"),
    user_id: str | None = typer.Option(None, "--user-id", help="Limit to one user"),
    limit: int | None = typer.Option(None, "--limit", help="Max pages to reindex"),
) -> None:
    """Re-chunk + re-embed active wiki pages into rag_documents / document_chunks.

    Use after wiki pages were saved without embeddings (empty rag_search /
    wiki_query), or after changing chunk settings.

    Examples:
        python -m cli rag reindex-wiki
        python -m cli rag reindex-wiki --tenant-id 01ABC --limit 20
    """
    asyncio.run(_reindex_wiki_async(tenant_id=tenant_id, user_id=user_id, limit=limit))


async def _reembed_async(*, batch: int, dry_run: bool) -> None:
    from app.core.database import get_db
    from app.modules.rag.services.rag_service import RagService

    async for db in get_db():
        service = RagService(db)
        count = await service.reembed_stale_chunks(batch_size=batch, dry_run=dry_run)
        if dry_run:
            console.print(f"[yellow]Dry run[/yellow] — [cyan]{count}[/cyan] chunk(s) need re-embedding")
        else:
            console.print(f"[green]Re-embedded[/green] [cyan]{count}[/cyan] chunk(s)")
        return


async def _reindex_wiki_async(
    *,
    tenant_id: str | None,
    user_id: str | None,
    limit: int | None,
) -> None:
    from app.core.database import get_db
    from app.modules.wiki.services.wiki_service import WikiService

    async for db in get_db():
        service = WikiService(db)
        stats = await service.reindex_all(tenant_id=tenant_id, user_id=user_id, limit=limit)
        console.print(
            f"[green]Wiki reindex[/green] total={stats['total']} "
            f"ok={stats['ok']} failed={stats['failed']} skipped={stats['skipped']}"
        )
        return

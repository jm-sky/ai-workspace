"""RAG retrieval-quality eval runner (plan 009 `eval-harness`).

Ingests the corpus referenced by the golden set, runs `RagService.search`
for every question, and scores retrieval against the golden set's
`relevant_docs` using the metrics in `metrics.py`. Exits non-zero (CI gate)
when any aggregate metric falls below its threshold.

Requires a configured `OPENROUTER_API_KEY` (real embedding calls) and a
reachable Postgres/pgvector — this is a live-system check, not a unit test.

Usage:
    python -m evals.rag.runner
    python -m evals.rag.runner --golden-set evals/rag/golden_set.jsonl --limit 5
    python -m evals.rag.runner --skip-ingest   # corpus already ingested
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.common.id_utils import generate_id  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.modules.rag.services.rag_service import RagService  # noqa: E402
from app.modules.tenants.service import TenantContext  # noqa: E402
from evals.rag.metrics import aggregate, score_question  # noqa: E402

DEFAULT_GOLDEN_SET = Path(__file__).parent / "golden_set.jsonl"
CORPUS_ROOT = Path(os.environ.get("EVAL_CORPUS_ROOT", "/repo"))

# Placeholder thresholds — tune once a real embedding model has a measured
# baseline on this golden set (dec. #1: eval-harness runs before embed-swap
# picks a final model).
DEFAULT_THRESHOLDS = {
    "hit_rate": 0.7,
    "mrr": 0.5,
    "context_precision": 0.3,
    "context_recall": 0.6,
}


def load_golden_set(path: Path) -> list[dict]:
    questions = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


async def ensure_corpus_ingested(
    service: RagService,
    tenant_ctx: TenantContext,
    doc_paths: set[str],
) -> None:
    existing, _total = await service.list_documents(tenant_ctx=tenant_ctx, limit=200)
    existing_titles = {doc.title for doc in existing}

    for rel_path in sorted(doc_paths):
        if rel_path in existing_titles:
            continue
        file_path = CORPUS_ROOT / rel_path
        if not file_path.exists():
            print(f"WARNING: corpus file not found, skipping: {file_path}", file=sys.stderr)
            continue
        content = file_path.read_text(encoding="utf-8")
        response, chunks = await service.ingest_paste(tenant_ctx=tenant_ctx, title=rel_path, content=content)
        await service.run_chunk_ingest(
            document_id=response.id,
            tenant_id=tenant_ctx.tenant_id,
            user_id=tenant_ctx.user_id,
            chunks=chunks,
        )
        print(f"Ingested: {rel_path} ({len(chunks)} chunks)")


async def _ensure_eval_tenant(db: AsyncSession, *, tenant_id: str, user_id: str) -> None:
    """Create throwaway tenant/user rows so rag_documents' FKs are satisfiable.

    Imports every module's SQLAlchemy models first — otherwise cross-module FK
    targets (e.g. users.active_team_id -> teams.id) fail to resolve.
    """
    import importlib

    for module in [
        "app.modules.agent.db_models",
        "app.modules.auth.db_models",
        "app.modules.gear.db_models",
        "app.modules.gear_settings.db_models",
        "app.modules.integrations.db_models",
        "app.modules.logs.db_models",
        "app.modules.memory.db_models",
        "app.modules.rag.db_models",
        "app.modules.settings.db_models",
        "app.modules.teams.db_models",
        "app.modules.tenants.db_models",
        "app.modules.two_factor.db_models",
        "app.modules.users.db_models",
        "app.modules.workspace_config.db_models",
    ]:
        importlib.import_module(module)

    from app.modules.auth.db_models import UserDB
    from app.modules.tenants.db_models import TenantDB

    db.add(UserDB(id=user_id, email=f"{user_id.lower()}@eval.local", name="RAG Eval", hashed_password="x"))
    await db.flush()
    db.add(TenantDB(id=tenant_id, name="RAG Eval", owner_id=user_id))
    await db.flush()
    await db.commit()


async def run(args: argparse.Namespace) -> int:
    from app.core.config import settings

    if not settings.ai.openrouter_api_key:
        print(
            "Cannot run eval: OPENROUTER_API_KEY is not configured. "
            "The harness needs a real embedding model to measure retrieval quality.",
            file=sys.stderr,
        )
        return 2

    golden_set = load_golden_set(args.golden_set)
    doc_paths = {path for item in golden_set for path in item["relevant_docs"]}

    reuse_tenant = bool(args.tenant_id and args.user_id)
    tenant_id = args.tenant_id or generate_id()
    user_id = args.user_id or generate_id()

    async with AsyncSessionLocal() as db:
        if not reuse_tenant:
            await _ensure_eval_tenant(db, tenant_id=tenant_id, user_id=user_id)

        service = RagService(db)
        tenant_ctx = TenantContext(tenant_id=tenant_id, user_id=user_id, tenant_role="member")

        if not args.skip_ingest:
            await ensure_corpus_ingested(service, tenant_ctx, doc_paths)

        per_question = []
        rows = []
        for item in golden_set:
            hits = await service.search(
                tenant_ctx=tenant_ctx,
                query=item["question"],
                limit=args.limit,
            )
            retrieved_titles = [hit.title for hit in hits]
            metrics = score_question(retrieved_titles, item["relevant_docs"])
            per_question.append(metrics)
            rows.append({"id": item["id"], "lang": item["lang"], **metrics.__dict__})

        overall = aggregate(per_question)

    print("\n--- Per-question ---")
    for row in rows:
        print(
            f"{row['id']:>8} [{row['lang']}] hit={row['hit_rate']:.2f} "
            f"mrr={row['mrr']:.2f} precision={row['context_precision']:.2f} "
            f"recall={row['context_recall']:.2f}"
        )

    print("\n--- Aggregate ---")
    thresholds = DEFAULT_THRESHOLDS
    failed = []
    for name, value in overall.__dict__.items():
        threshold = thresholds[name]
        status = "OK" if value >= threshold else "FAIL"
        if status == "FAIL":
            failed.append(name)
        print(f"{name:>20}: {value:.3f} (threshold {threshold}) [{status}]")

    if args.output:
        args.output.write_text(
            json.dumps({"per_question": rows, "aggregate": overall.__dict__}, indent=2),
            encoding="utf-8",
        )
        print(f"\nWrote report: {args.output}")

    if failed:
        print(f"\nGATE FAILED: {', '.join(failed)} below threshold", file=sys.stderr)
        return 1

    print("\nGATE PASSED")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden-set", type=Path, default=DEFAULT_GOLDEN_SET)
    parser.add_argument("--limit", type=int, default=8, help="top-K chunks per query")
    parser.add_argument("--skip-ingest", action="store_true", help="corpus already ingested")
    parser.add_argument("--tenant-id", type=str, default=None, help="reuse an existing eval tenant")
    parser.add_argument("--user-id", type=str, default=None, help="reuse an existing eval user")
    parser.add_argument("--output", type=Path, default=None, help="write JSON report to this path")
    args = parser.parse_args()

    exit_code = asyncio.run(run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

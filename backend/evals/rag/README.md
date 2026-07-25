# RAG eval harness

Measures retrieval quality (not generation quality) against a golden set of
questions with known-relevant source documents. Built for plan
[009](../../../docs/plans/2026-07-25--009--phase-4-retrieval-quality.md) —
read that plan for the "why", this file is the "how".

## What it measures

Four metrics, computed per question and averaged:

| Metric | Definition |
|---|---|
| `hit_rate` | 1.0 if any relevant document appears anywhere in the top-K retrieved chunks, else 0.0 |
| `mrr` | 1 / rank of the first relevant hit (0 if none found) |
| `context_precision` | fraction of the top-K retrieved chunks that come from a relevant document |
| `context_recall` | fraction of the known-relevant documents that were found anywhere in the top-K |

These are the RAGAS `context_precision`/`context_recall` definitions, computed
against **known-relevant documents** rather than an LLM judge — no generation
step, no LLM-as-judge call. That's a deliberate simplification: RAGAS's other
metrics (`faithfulness`, `answer_relevancy`) score a *generated answer*, which
needs an LLM call regardless of which library computes it. We don't have a
live model in every environment this runs in, so the harness sticks to
metrics that only need the retriever. If you want the full RAGAS/DeepEval
metric set (as originally sketched in plan 009), swap `metrics.py`'s callers
in `runner.py` for the real libraries — the golden-set format and the
ingest/retrieve loop stay the same.

## Running it

Needs a real `OPENROUTER_API_KEY` (embeds the golden-set questions and the
ingested corpus) and a reachable Postgres/pgvector. The runner checks for the
key up front and exits with code `2` (not a gate failure) if it's missing.

```bash
# first run: ingests the corpus referenced by golden_set.jsonl, then evaluates
python -m evals.rag.runner

# re-run against the same tenant without re-ingesting
python -m evals.rag.runner --tenant-id <id> --user-id <id> --skip-ingest

# write a JSON report
python -m evals.rag.runner --output evals/rag/last-run.json
```

Exit codes: `0` = all thresholds met, `1` = gate failed (some metric below
threshold — fails CI), `2` = couldn't run at all (missing config).

In this repo's Docker dev setup, `docker-compose.dev.yml` mounts `docs/` and
`CLAUDE.md` read-only into the `app` container at `/repo` — that's where the
golden set's `relevant_docs` paths are resolved from
(`EVAL_CORPUS_ROOT`, default `/repo`). In CI, point `EVAL_CORPUS_ROOT` at the
checked-out repo root instead — no Docker involved there.

## Golden set format (`golden_set.jsonl`)

One JSON object per line:

```json
{"id": "en-001", "lang": "en", "question": "...", "relevant_docs": ["docs/MVP.md"]}
```

- `id` — stable identifier (`{lang}-{NNN}`), shows up in per-question output.
- `lang` — `en` or `pl`. Keep both languages represented (multilingual
  embeddings is the whole point of plan 009's model decision).
- `question` — natural-language question a real user might ask.
- `relevant_docs` — paths (relative to `EVAL_CORPUS_ROOT`) of documents that
  should be retrievable for this question. These become the RAG document
  `title` at ingest time, so a hit's `title` matching one of these paths
  counts as a relevant hit.

**Current set: 34 questions (18 EN, 16 PL)**, built from this session's
actual reading of `docs/MVP.md`, `CLAUDE.md`, `docs/plans/008`,
`docs/plans/009`, and `docs/issues/023`. Plan 009 calls for a **human
review** pass and growing this to 100–200 questions from a wider corpus slice
— treat the current set as a first draft, not a finished baseline.

### Adding questions

1. Pick a real `docs/` file (or `CLAUDE.md`) you can answer questions about
   confidently — don't invent facts, write questions from content you've
   actually read.
2. Add a line to `golden_set.jsonl` with a fresh `id`, the question, and the
   file's path in `relevant_docs`. Multiple relevant docs are fine if the
   answer genuinely spans files.
3. Have a second person (or a fresh read) confirm the file actually answers
   the question — this is the "human review" the plan calls for.
4. Run `python -m evals.rag.runner` and check the per-question line for your
   new `id` isn't a `hit_rate=0.00` outlier before committing (that usually
   means the relevant doc wasn't ingested, or the question is off-target).

## Thresholds

Defaults live in `runner.py`'s `DEFAULT_THRESHOLDS` — placeholders, not a
measured baseline (plan 009 dec. #1: no live model was evaluated to pick
these numbers in this environment). **Before wiring this into a CI gate**,
run it against your chosen embedding model, record the actual numbers, and
set thresholds a bit below that measured baseline — not before.

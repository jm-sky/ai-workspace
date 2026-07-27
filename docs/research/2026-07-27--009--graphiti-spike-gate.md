# Research 009 — Graphiti spike: gate metrics

**Status:** `in progress`
**Data:** 2026-07-27
**Parent plan:** [011 — Memory graph: facade + cutover na Graphiti](../plans/2026-07-25--011--memory-graph-graphiti.md)
**Etap:** 2 (spike scaffolding)

## Cel

Zmierzyć 6 metryk bramki go/no-go z planu 011 dla Graphiti jako alternatywnego backendu pamięci.

## Infrastruktura (gotowa)

| Element | Status | Szczegóły |
|---------|--------|-----------|
| `docker-compose.graphiti.yml` | ✅ | FalkorDB v4.20.1 na porcie 6383 |
| `GraphitiMemoryBackend` | ✅ | `create` + `search` zaimplementowane; `update`/`delete`/`list` → `NotImplementedError` |
| `PgVectorMemoryBackend` (facade) | ✅ | Wydzielony z MemoryService, 16 testów przechodzi bez zmian |
| `MemoryBackend` Protocol | ✅ | `base.py` — interfejs dla obu backendów |
| Spike runner (`evals/memory_graphiti/`) | ✅ | Fixtures: 2 tenantów × 2 userów × 10 dialogów, metryki bramki |
| `MEMORY_BACKEND` config | ✅ | Walidacja `pgvector|graphiti`, default `pgvector` |

## Bramka go/no-go — wyniki

| Kryterium | Próg | Zmierzone | Wynik |
|-----------|------|-----------|-------|
| Izolacja `group_id` | 0 wycieków | ⏭️ nie uruchomiono | ⏭️ SKIP |
| p95 `search` (warm) | < 3 s | ⏭️ nie uruchomiono | ⏭️ SKIP |
| Ingest 10 rozmów | < 5 min wall | ⏭️ nie uruchomiono | ⏭️ SKIP |
| RSS kontenera (idle) | < 2 GB | 124 MiB | ✅ PASS |
| Koszt ingestu | < 25k tok/rozmowę | ⏭️ nie uruchomiono | ⏭️ SKIP |
| Jakość vs pgvector | ≥ tyle samo faktów | ⏭️ nie uruchomiono | ⏭️ SKIP |

### Blokery

1. **`OPENROUTER_API_KEY` nie ustawiony w kontenerze** — Graphiti wymaga LLM do entity extraction. Bez klucza API ingest i search nie mogą się uruchomić.
2. FalkorDB reachable ✅ (po podłączeniu kontenera do `ai-workspace-network`).
3. `graphiti-core==0.29.2` zainstalowane w kontenerze (tymczasowo — nie w `pyproject.toml`).

### Jak uruchomić spike z kluczem API

```bash
# FalkorDB musi być w sieci ai-workspace-network:
docker network connect ai-workspace-network ai-workspace-graphiti

# Uruchom spike z kluczem:
docker exec -e OPENROUTER_API_KEY=sk-or-xxx ai-workspace-app \
  python -m evals.memory_graphiti.run_spike \
  --falkordb-url bolt://ai-workspace-graphiti:6379
```

## Werdykt

**🟡 INCOMPLETE** — infrastruktura gotowa, bramka czeka na uruchomienie z kluczem API. Nie ma sensu decydować go/no-go bez faktycznych wyników metryk.

Niezależnie od wyniku bramki, **etap 1 (facade) ma wartość sam w sobie** — `MemoryBackend` Protocol + `PgVectorMemoryBackend` pozwalają na czystą podmianę backendu bez zmian w MemoryService, toolach ani routerze.

## Następne kroki (po decyzji użytkownika)

1. Uruchomić spike z kluczem API i zmierzyć 5 pozostałych metryk
2. Na podstawie wyników: decyzja go/no-go
3. Jeśli go → etap 3+ (migracja, dual-read, cutover) per plan 011
4. Jeśli no-go → facade zostaje, lifecycle pamięci (decay/konsolidacja) realizujemy w pgvectorze

# Storage Layer Review - Round 3 (Operations)

> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Operational Reality
> Files Reviewed: storage/sqlite_store.py, storage/hybrid.py, storage/vector_store.py, storage/action_log.py, embedding/openai_embed.py, config.py, scripts/migrate_v2.py

## Baseline

- Live DB size: 26.01 MB (`data/memory.db`)
- Live rows: 3,299 nodes / 6,329 edges / 3,206 action_log rows
- SQLite mode: `journal_mode=wal`
- SQLite maintenance: `auto_vacuum=0`, no runtime `VACUUM`, no scheduled checkpointing
- Activity amplification: 295 `recall` rows produced 2,890 `node_activated` rows (9.8 per recall)

## Findings

### [Severity: CRITICAL]

**C01** Recall-side learning is broken against the live schema
- File: `storage/hybrid.py:263-271`, `storage/sqlite_store.py:24-56`
- Description: `_bcm_update()` writes `nodes.last_activated`, but the live `nodes` table does not have that column. The whole transaction is wrapped in `except Exception: pass`, so the write path can fail and roll back silently.
- Evidence: the live DB recorded 2,890 activations in the last 7 days, but 324 nodes had recent activation with `visit_count=0`.
- Impact: recall learning, recency tracking, and UCB normalization are not trustworthy in production. Failures are silent.

**C02** Concurrent edge writes are not protected by schema-level uniqueness or atomic update patterns
- File: `storage/sqlite_store.py:58-75`, `storage/sqlite_store.py:253-279`, `scripts/enrich/relation_extractor.py:184-205`, `scripts/enrich/graph_analyzer.py:688-707`, `storage/hybrid.py:212-245`
- Description: the `edges` table has no unique constraint on `(source_id, target_id, relation)`. `insert_edge()` blindly inserts, and the enrichment scripts use a check-then-insert pattern without a unique index. `_bcm_update()` also uses read-modify-write on JSON state (`theta_m`, `activity_history`) without optimistic locking.
- Impact: duplicate edges and lost learning updates become plausible as soon as multiple writers overlap.

### [Severity: HIGH]

**H01** WAL is enabled, but connection policy is inconsistent across operational code paths
- File: `storage/sqlite_store.py:11-18`, `scripts/daily_enrich.py:42-48`, `scripts/pruning.py:25-28`, `scripts/hub_monitor.py:25-28`
- Description: the shared store uses `busy_timeout=30000` and `foreign_keys=ON`, but `daily_enrich.py` uses `busy_timeout=5000`, and several scripts open raw SQLite connections without the shared pragma set.
- Impact: the same workload behaves differently depending on which entrypoint opened the connection. Under overlap, scripts will fail sooner than MCP calls.

**H02** Runtime backup and restore do not exist outside migration scripts
- File: `config.py:96-98`, `scripts/migrate_v2.py:51-59`, `scripts/migrate_v2.py:394-415`
- Description: `BACKUP_DIR` exists in config, but the only concrete backup flow is in `migrate_v2.py`. There is no runtime backup, restore, or integrity-check procedure for the production server.
- Impact: operational recovery depends on ad hoc file copies and luck, not a tested process.

### [Severity: MEDIUM]

**M01** Disk growth is unbounded and cleanup will not reclaim space automatically
- File: `storage/sqlite_store.py:134-224`, `storage/hybrid.py:332-380`, `config.py:96-98`
- Description: every recall logs one summary row plus up to ten activation rows. There is no retention policy, no `VACUUM`, and `auto_vacuum=0`.
- Impact: DB size will drift upward even if pruning and edge deletion keep logical row counts under control. A 10x linear extrapolation from the current 26.01 MB baseline is already about 260 MB before action_log growth dominates.

**M02** Startup initialization is not a migration engine
- File: `storage/sqlite_store.py:21-226`, `server.py:341-342`
- Description: `init_db()` only creates missing tables and indexes. It does not reconcile drift in already-existing tables.
- Impact: restarting the server does not repair missing production schema such as `meta`, `recall_log`, or `nodes.last_activated`.

## Operational Assessment

- Concurrent DB writes: acceptable only for a low-volume single-user workflow. Not safe for unattended overlapping recall and enrichment traffic.
- WAL mode: correctly enabled, but not enough by itself because the write paths are still serialized and partly inconsistent.
- Lock contention: likely under overlap because recall, promotion, and enrichment all write.
- Data corruption scenarios: the bigger risk is silent logical corruption or silent rollback, not raw SQLite page corruption.
- Backup and restore: migration-only, not operationalized.
- Disk growth: action_log and FTS will dominate unless retention and vacuuming are added.

## Summary

- Immediate production break: recall-side learning can fail silently because code writes a missing node column.
- First scale break: duplicate/lost-write risk and lock contention once multiple writers overlap.
- Missing safety net: no runtime backup, no retention, no schema drift check on startup.

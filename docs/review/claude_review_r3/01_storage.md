# Storage Layer Review - Round 3 (Operations)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Operational Reality
> Files Reviewed: storage/sqlite_store.py, storage/hybrid.py, storage/vector_store.py, storage/action_log.py, embedding/openai_embed.py, config.py

## Findings

### [Severity: CRITICAL]

**C01** Connection leak under exceptions in write functions
- File: `storage/sqlite_store.py:242-248` (insert_node), `storage/sqlite_store.py:265-279` (insert_edge), `storage/sqlite_store.py:356-371` (update_tiers)
- Description: insert_node, insert_edge, update_tiers에 try/finally 블록이 없다. conn.execute() 또는 conn.commit() 도중 예외 발생 시 conn.close()가 호출되지 않아 연결이 누수된다. SQLite는 프로세스당 파일 락을 사용하므로, 누수된 연결이 GC되기 전까지 다른 연결의 쓰기를 차단할 수 있다.
- Impact: 반복적 예외 발생 시 DB 락 누적 → busy_timeout 초과 → 전체 시스템 쓰기 실패. MCP 서버 재시작 필요.
- Recommendation: 모든 쓰기 함수에 `try/finally: conn.close()` 패턴 적용. 또는 context manager(`with conn:`) 사용.

**C02** Graph cache race condition (no lock)
- File: `storage/hybrid.py:26-28` (_GRAPH_CACHE, _GRAPH_CACHE_TS globals)
- Description: _GRAPH_CACHE와 _GRAPH_CACHE_TS가 threading.Lock 없이 전역 변수로 관리된다. MCP 서버가 단일 프로세스라도, asyncio 환경에서 두 개의 코루틴이 동시에 캐시 만료를 감지하면 양쪽 모두 get_all_edges() + build_graph()를 실행한다. 더 심각한 경우: 한 코루틴이 _GRAPH_CACHE를 갱신하는 중에 다른 코루틴이 읽으면 inconsistent state.
- Impact: (1) 불필요한 이중 그래프 빌드 (성능), (2) 부분 갱신된 캐시 참조 (정합성), (3) NetworkX DiGraph는 thread-safe하지 않아 순회 중 변경 시 iterator invalidation.
- Recommendation: `asyncio.Lock()` 또는 `threading.Lock()`으로 캐시 접근 직렬화.

**C03** Lost BCM updates under concurrent writes
- File: `storage/hybrid.py:200-278` (_bcm_update)
- Description: BCM 업데이트가 read-modify-write 패턴을 사용한다: (1) theta_m, activity_history를 SELECT, (2) Python에서 계산, (3) UPDATE로 저장. 두 세션이 동시에 recall()을 호출하면 같은 노드에 대해 양쪽이 동일한 theta_m을 읽고, 각자 계산한 뒤 마지막 쓰기가 이전 쓰기를 덮어쓴다. activity_history JSON 배열도 동일한 문제 — 한쪽의 기록이 사라진다.
- Impact: BCM 학습 데이터 손실 → theta_m 드리프트 → 검색 품질 저하 (silent corruption, 발견 어려움).
- Recommendation: (1) `UPDATE nodes SET theta_m = ... WHERE id = ? AND theta_m = ?` (optimistic locking), 또는 (2) 단일 SQL로 atomic update 구현.

---

### [Severity: HIGH]

**H01** No retry logic anywhere in storage layer
- File: `storage/sqlite_store.py:15-17` (PRAGMA busy_timeout=30000)
- Description: busy_timeout=30초가 유일한 동시성 보호다. 30초 이후에도 잠금이 풀리지 않으면 `sqlite3.OperationalError: database is locked` 예외가 발생하고, 재시도 없이 바로 실패한다. enrichment 파이프라인(CONCURRENT_WORKERS=10)이 돌아가는 동안 MCP 도구가 호출되면 쓰기 경합이 현실적으로 발생한다.
- Impact: 사용자의 remember/recall 호출이 enrichment와 충돌 시 30초 대기 후 에러 반환.
- Recommendation: exponential backoff retry (config.py에 MAX_RETRIES=3, RETRY_BACKOFF=2.0 이미 정의되어 있으나 storage layer에서 미사용).

**H02** Silent exception swallowing in hybrid.py
- File: `storage/hybrid.py:274-275` (BCM), `storage/hybrid.py:485-486` (SPRT), `storage/hybrid.py:377-380` (action_log)
- Description: 최소 4곳에서 `except Exception: pass` 패턴으로 모든 예외를 삼킨다. 로깅이 전혀 없어서 BCM 학습 실패, SPRT 누적 실패, action_log 기록 실패가 발생해도 아무 흔적이 남지 않는다.
- Impact: 운영 중 데이터 무결성 문제가 발생해도 진단 불가. "검색 품질이 안 좋다"는 증상만 보이고 원인 추적 불가능.
- Recommendation: `logging.warning()` 또는 `logging.error()` 추가. 최소한 예외 타입과 메시지는 기록.

**H03** OpenAI embedding API zero resilience
- File: `embedding/openai_embed.py:18-22` (embed_text)
- Description: OpenAI API 호출에 재시도, 타임아웃, 레이트 리밋 처리, 캐싱이 모두 없다. API 일시 장애, 네트워크 지연, 429 Too Many Requests 모두 즉시 RuntimeError로 전파되어 remember()와 recall() 전체를 실패시킨다.
- Impact: OpenAI API 불안정 시 MCP 전체 기능 마비. 특히 batch enrichment(CONCURRENT_WORKERS=10) 중 레이트 리밋 발생 확률 높음.
- Recommendation: tenacity 라이브러리로 retry + exponential backoff. OpenAI SDK의 `max_retries` 파라미터 활용 (기본값 2).

**H04** SPRT promotion_candidate flag never resets
- File: `storage/hybrid.py:480-482` (SPRT candidate setting)
- Description: _sprt_check()가 True를 반환하면 노드의 promotion_candidate=1로 설정하지만, 이후 promote_node()가 실패하거나 호출되지 않아도 플래그가 영구히 1로 남는다. 반대 경우(LLR < B threshold로 rejection) 시에도 candidate=0으로 리셋하는 로직이 없다.
- Impact: (1) 한 번 candidate된 노드는 analyze_signals()에서 계속 추천됨 (noise), (2) rejection된 노드도 candidate 상태 유지 → 잘못된 추천.
- Recommendation: promote 성공/실패/rejection 시 promotion_candidate 리셋 로직 추가. TTL 기반 자동 만료도 고려.

**H05** Stale UCB visit_count from cached graph
- File: `storage/hybrid.py:120,130` (UCB visit_count), `storage/hybrid.py:26` (_GRAPH_CACHE TTL)
- Description: UCB 탐색이 _GRAPH_CACHE의 NetworkX graph에서 visit_count를 읽지만, BCM 업데이트는 DB에 직접 쓴다. 그래프 캐시 TTL이 만료되기 전까지 UCB는 오래된 visit_count를 사용한다. config.py에서 TTL 값을 확인할 수 없었으나, hybrid.py에 하드코딩된 것으로 추정.
- Impact: UCB의 exploration-exploitation 균형이 왜곡됨 → 이미 많이 탐색된 노드가 다시 선택되거나, 탐색이 부족한 노드가 무시됨.
- Recommendation: BCM 업데이트 후 graph cache를 invalidate하거나, UCB에서 DB 직접 조회.

---

### [Severity: MEDIUM]

**M01** N+1 queries in BCM update
- File: `storage/hybrid.py:214-216`
- Description: activated_edges 루프 내에서 노드별로 개별 SELECT 쿼리를 실행한다. recall 결과가 20개이고 각각 평균 3개의 엣지를 가지면 ~60회 개별 쿼리 발생.
- Impact: recall() 한 번에 수십 개의 DB 왕복. 3,255노드/6,324엣지 규모에서 체감 가능한 지연.
- Recommendation: `WHERE id IN (...)` bulk SELECT + dict mapping.

**M02** ZeroDivisionError risk in theta_m calculation
- File: `storage/hybrid.py:235-236`
- Description: `history = (history + [v_i])[-BCM_HISTORY_WINDOW:]` 이후 `sum(h**2 for h in history) / len(history)`. history가 빈 리스트이면서 새 값을 추가하므로 실제로 len >= 1이지만, activity_history 컬럼이 NULL이거나 빈 JSON이면서 v_i 계산 전에 예외가 발생할 경우 빈 리스트로 도달 가능.
- Impact: ZeroDivisionError → BCM 전체 실패 → except Exception: pass로 삼켜짐 → silent failure.
- Recommendation: `max(len(history), 1)`로 방어.

**M03** No backup/restore implementation
- File: `config.py` (BACKUP_DIR 정의만)
- Description: config.py에 `BACKUP_DIR = DATA_DIR / "backup"` 경로가 정의되어 있지만, 실제 백업 생성/복원 로직이 storage layer에 없다. SQLite의 `.backup()` API나 파일 복사 메커니즘이 구현되지 않았다.
- Impact: DB 손상 시 복구 불가. WAL 파일 손상, 디스크 오류, 마이그레이션 실패 시 데이터 전체 손실 위험.
- Recommendation: (1) daily_enrich.py 실행 전 자동 백업, (2) `sqlite3.Connection.backup()` API 활용, (3) WAL checkpoint 후 파일 복사.

**M04** vector_store singleton race condition
- File: `storage/vector_store.py:9-10` (_client, _collection globals)
- Description: _get_collection()에서 `if _collection is None` 체크와 초기화 사이에 경합 가능. 두 코루틴이 동시 진입하면 ChromaDB PersistentClient가 두 번 생성될 수 있다.
- Impact: ChromaDB가 같은 디렉토리에 두 개의 클라이언트를 열면 파일 락 충돌 또는 데이터 불일치.
- Recommendation: Lock 추가 또는 모듈 로드 시 eager initialization.

**M05** No connection validation before queries
- File: `storage/hybrid.py:82-90` (_traverse_sql), `storage/hybrid.py:200` (_bcm_update)
- Description: `sqlite_store._connect()` 반환값에 대한 유효성 검증 없이 바로 execute() 호출. DB 파일이 삭제되거나 권한이 변경된 경우 연결 자체는 성공하지만 execute()에서 실패.
- Impact: 불명확한 에러 메시지로 디버깅 어려움.
- Recommendation: 연결 후 `PRAGMA integrity_check` (무거움) 대신 `SELECT 1` 같은 가벼운 health check.

**M06** Recursive CTE parameter explosion
- File: `storage/hybrid.py:60-78`
- Description: Graph traversal CTE의 `WHERE id NOT IN (...)` 절에 seed_ids가 3번 반복된다. seed_ids가 100개면 300개의 placeholder. SQLite의 SQLITE_MAX_VARIABLE_NUMBER 기본값은 999이므로 333개 이상의 seed에서 쿼리 실패.
- Impact: 대량 seed를 가진 recall에서 런타임 에러.
- Recommendation: 임시 테이블에 seed_ids를 INSERT 후 JOIN, 또는 seed_ids 개수 제한.

---

### [Severity: LOW]

**L01** Missing PRAGMA optimizations
- File: `storage/sqlite_store.py:15-17`
- Description: `PRAGMA synchronous=NORMAL` (WAL 모드에서 안전), `PRAGMA cache_size` (기본 2MB → 더 큰 값), `PRAGMA mmap_size` 미설정.
- Impact: 읽기 성능이 최적이 아님. 3,255노드 규모에서는 미미하지만 10x 성장 시 체감.
- Recommendation: WAL 모드에서 `synchronous=NORMAL`은 안전하면서 성능 개선.

**L02** ChromaDB client cleanup absent
- File: `storage/vector_store.py`
- Description: ChromaDB PersistentClient에 대한 close()/cleanup() 메서드가 없다. 프로세스 종료 시 암묵적 정리에 의존.
- Impact: 비정상 종료 시 ChromaDB 내부 파일 락 잔존 가능 (재시작 시 자동 복구되지만 지연 발생).
- Recommendation: atexit 핸들러 또는 context manager.

**L03** query[:80] truncation in BCM context log
- File: `storage/hybrid.py:247-261`
- Description: BCM 재공고화(reconsolidation)에서 쿼리를 80자로 잘라 context_log에 저장. 한국어 쿼리의 경우 80자가 약 40단어로 대부분 충분하지만, 긴 기술 쿼리에서 핵심 키워드가 잘릴 수 있다.
- Impact: context_log 기반 분석 시 불완전한 쿼리 정보.
- Recommendation: 150자 또는 설정 가능한 값으로 변경.

**L04** No connection pooling
- File: `storage/sqlite_store.py:11-18` (_connect)
- Description: 매 함수 호출마다 새 연결 생성 후 닫음. 연결 풀이 없어서 PRAGMA 설정(WAL, busy_timeout, foreign_keys)이 매번 재실행된다.
- Impact: 미미한 성능 오버헤드 (SQLite 연결 생성은 빠름). 하지만 PRAGMA 재설정 비용 누적.
- Recommendation: 현재 규모에서는 낮은 우선순위. 성능 문제 발생 시 연결 풀 도입.

---

### [Severity: INFO]

**I01** config.py에 MAX_RETRIES=3, RETRY_BACKOFF=2.0이 정의되어 있으나 storage layer 어디에서도 사용되지 않음. enrichment 파이프라인 전용으로 추정.

**I02** action_log.py의 설계는 견고함 — 외부 트랜잭션 재사용(own_conn=False), 예외 안전화, set-and-forget 패턴. Storage layer에서 가장 운영 안전한 모듈.

**I03** SQLite WAL 모드에서 checkpoint가 자동으로 실행되지만(1000페이지 기본), 명시적 checkpoint 제어가 없음. WAL 파일이 지속 성장할 수 있음.

## Coverage

- Files reviewed: 6/6 (sqlite_store.py, hybrid.py, vector_store.py, action_log.py, openai_embed.py, config.py)
- Functions verified: 28/28 (all public methods in storage layer)
- Spec sections checked: N/A (Round 3 = operational perspective, not spec alignment)

## Summary

- CRITICAL: 3
- HIGH: 5
- MEDIUM: 6
- LOW: 4
- INFO: 3

**Top 3 Most Impactful Findings:**

1. **C03 (Lost BCM updates)** — 가장 위험. 동시 세션에서 학습 데이터가 silent하게 손실되며, 검색 품질 저하로만 나타나 원인 추적이 극히 어려움. read-modify-write 패턴의 구조적 문제.
2. **H03 (OpenAI API zero resilience)** — 가장 빈번. 외부 API 의존성에 재시도/폴백이 전혀 없어서, OpenAI 일시 장애 시 remember/recall 전체가 즉시 마비됨. config.py에 retry 상수가 이미 있으므로 적용만 하면 됨.
3. **C01 (Connection leak)** — 가장 파급력 큼. 연결 누수가 누적되면 DB 전체 잠금으로 이어져 모든 기능이 멈춤. try/finally 한 줄로 해결 가능하므로 즉시 수정 권장.

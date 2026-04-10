"""MCP Memory Server — 3중 하이브리드 검색 외부 메모리."""

import sys
import threading
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "memory",
    instructions="External memory system with hybrid search (Vector + FTS5 + Graph). "
    "Use remember() to store, recall() to search, get_context() for session summary.",
)

# ── Lazy initialization ──────────────────────────────────────────
# 무거운 import + DB init + verify를 백그라운드 스레드로 실행.
# mcp.run()이 즉시 시작되어 stdio handshake가 타임아웃 없이 완료된다.
# 도구 호출 시 _ready.wait()로 init 완료를 보장.
_ready = threading.Event()

# 모듈 레벨 플레이스홀더 — _init_worker()에서 할당
PROMOTE_LAYER = None
validate_node_type = None
suggest_closest_type = None
check_access = None
LAYER_PERMISSIONS = None
_remember = None
_recall = None
_get_context = None
_save_session = None
_visualize = None
_analyze_signals = None
_promote_node = None
_get_becoming = None
_ontology_review = None
_generate_dashboard = None
insert_session_event = None
resolve_session_event = None
_export_ontology = None
_flag_node = None


def _init_worker():
    """백그라운드 초기화: import, DB init, schema sync, verification."""
    global PROMOTE_LAYER, validate_node_type, suggest_closest_type
    global check_access, LAYER_PERMISSIONS
    global _remember, _recall, _get_context, _save_session
    global _visualize, _analyze_signals
    global _promote_node, _get_becoming
    global _ontology_review, _generate_dashboard
    global insert_session_event, resolve_session_event
    global _export_ontology, _flag_node

    from config import OPENAI_API_KEY, PROMOTE_LAYER as _PL
    PROMOTE_LAYER = _PL

    from ontology.validators import validate_node_type as _vnt, suggest_closest_type as _sct
    validate_node_type = _vnt
    suggest_closest_type = _sct

    from storage.sqlite_store import (
        init_db, sync_schema,
        insert_session_event as _ise,
        resolve_session_event as _rse, export_ontology as _eo,
    )
    insert_session_event = _ise
    resolve_session_event = _rse
    _export_ontology = _eo

    from utils.access_control import check_access as _ca, LAYER_PERMISSIONS as _lp
    check_access = _ca
    LAYER_PERMISSIONS = _lp

    if not OPENAI_API_KEY:
        import warnings
        warnings.warn("OPENAI_API_KEY not set — embedding features will fail")

    from tools.remember import remember as r
    from tools.recall import recall as rc
    from tools.get_context import get_context as gc
    from tools.save_session import save_session as ss
    from tools.visualize import visualize as vz
    from tools.analyze_signals import analyze_signals as az
    from tools.promote_node import promote_node as pn
    from tools.get_becoming import get_becoming as gb
    from scripts.ontology_review import run_review as orv
    from scripts.dashboard import generate_dashboard as gd
    from tools.flag_node import flag_node as fn

    _remember = r
    _recall = rc
    _get_context = gc
    _save_session = ss
    _visualize = vz
    _analyze_signals = az
    _promote_node = pn
    _get_becoming = gb
    _ontology_review = orv
    _generate_dashboard = gd
    _flag_node = fn

    # DB 초기화 + 스키마 동기화
    init_db()
    sync_schema()

    # quick verify (실패해도 서버 정상 작동)
    try:
        from scripts.eval.verify import run_all
        run_all(quick=True)
    except Exception:
        pass

    # P0: 모델 + 캐시 사전 로드 (콜드 스타트 제거)
    try:
        from embedding import embed_text
        embed_text("warmup")
    except Exception:
        pass
    try:
        from storage.vector_store import _ensure_cache
        _ensure_cache()
    except Exception:
        pass
    try:
        from storage.reranker import _load_model as _load_reranker
        _load_reranker()
    except Exception:
        pass

    _ready.set()


threading.Thread(target=_init_worker, daemon=True).start()


@mcp.tool()
def remember(
    content: str,
    type: str = "Unclassified",
    tags: str = "",
    project: str = "",
    metadata: dict | None = None,
    confidence: float = 1.0,
    source: str = "claude",
    actor: str = "system",
    retrieval_hints: dict | None = None,
    parent_id: int | None = None,
    parent_relation: str = "contains",
) -> dict:
    """Store a memory node with automatic embedding and relationship detection.

    Args:
        content: The memory content to store (decision, insight, pattern, etc.)
        type: Node type — Decision, Failure, Pattern, Identity, Preference, Goal,
              Insight, Question, Metaphor, Connection, Evolution, Breakthrough,
              Experiment, Tool, Principle, Workflow, AntiPattern, Project, Tension,
              Narrative, Skill, Conversation, Unclassified
        tags: Comma-separated tags (e.g. "orchestration,v4.0,design")
        project: Project name (orchestration, portfolio, tech-review, monet-lab)
        metadata: Additional key-value metadata
        confidence: Confidence level 0.0-1.0 (default 1.0)
        source: Source of memory — claude, user, hook, obsidian (default claude)
        retrieval_hints: Retrieval context hints (when_needed, related_queries, context_keys)
        parent_id: Parent node ID — creates parent→child edge automatically
        parent_relation: Relation type for parent edge (default: contains)
    """
    _ready.wait()
    # ── [A-13 통합] 타입 검증 블록 ─────────────────────────────────────────
    deprecated_warning: str | None = None

    valid, correction = validate_node_type(type)

    if valid:
        # 유효 타입 — 대소문자 교정이 있으면 적용
        if correction:
            type = correction  # e.g., "pattern" → "Pattern"

    else:
        if correction:
            # Deprecated 타입 — replaced_by로 자동 교정 + 경고
            deprecated_warning = (
                f"Type '{type}' is deprecated. Auto-converted to '{correction}'."
            )
            type = correction  # 교정 후 정상 저장 진행

        else:
            # 완전히 없는 타입 — 저장 차단 + content 기반 추천
            suggestion = suggest_closest_type(content)
            return {
                "node_id": None,
                "type": type,
                "project": project,
                "auto_edges": [],
                "error": f"Unknown node type: '{type}'.",
                "suggestion": suggestion,
                "message": (
                    f"Validation failed: unknown type '{type}'. "
                    f"Suggested: '{suggestion}'"
                ),
            }
    # ── [타입 검증 끝] ─────────────────────────────────────────────────────

    # ── [A-10 F1: L4/L5 접근 제어] ────────────────────────────────────────
    target_layer = PROMOTE_LAYER.get(type)
    if target_layer in (4, 5):
        allowed = LAYER_PERMISSIONS.get(target_layer, {}).get("write", ["paul"])
        actor_base = actor.split(":")[0] if ":" in actor else actor
        if "all" not in allowed and actor_base not in allowed and actor not in allowed:
            return {
                "node_id": None,
                "type": type,
                "project": project,
                "auto_edges": [],
                "error": f"Access denied: L{target_layer} write requires actor in {allowed}, got '{actor}'",
                "message": f"A-10 F1: '{actor}' cannot create L{target_layer} node ({type})",
            }

    result = _remember(
        content=content,
        type=type,
        tags=tags,
        project=project,
        metadata=metadata,
        confidence=confidence,
        source=source,
        retrieval_hints=retrieval_hints,
        parent_id=parent_id,
        parent_relation=parent_relation,
    )

    # Deprecated 타입 사용 시 경고 추가
    if deprecated_warning:
        result["warning"] = deprecated_warning

    return result


MAX_TOP_K = 50


@mcp.tool()
def recall(
    query: str,
    type_filter: str = "",
    project: str = "",
    top_k: int = 5,
    mode: str = "auto",
    mutate: bool = True,
) -> dict:
    """Search memories using 3-way hybrid search (Vector + FTS5 + Graph).

    Returns up to top_k results ranked by Reciprocal Rank Fusion,
    with relationship paths and content previews.

    Args:
        query: Search query (natural language or keywords)
        type_filter: Filter by node type (e.g. "Decision", "Pattern")
        project: Filter by project name
        top_k: Number of results to return (default 5, max 50)
        mode: Search mode — "auto" (default), "focus" (strong connections), "dmn" (exploratory)
        mutate: When false, skip learning/log/stat write-back for read-only evaluation
    """
    _ready.wait()
    top_k = min(top_k, MAX_TOP_K)
    return _recall(
        query=query,
        type_filter=type_filter,
        project=project,
        top_k=top_k,
        mode=mode,
        mutate=mutate,
    )


@mcp.tool()
def get_context(project: str = "") -> dict:
    """Get a compact context summary (~200 tokens) for session start.

    Returns recent decisions, open questions, insights, and failures.

    Args:
        project: Filter by project name (empty = all projects)
    """
    _ready.wait()
    return _get_context(project=project)


@mcp.tool()
def save_session(
    session_id: str = "",
    summary: str = "",
    decisions: list[str] | None = None,
    unresolved: list[str] | None = None,
    project: str = "",
    active_pipeline: str = "",
) -> dict:
    """Save structured session data (summary, decisions, unresolved items).

    Args:
        session_id: Unique session identifier (auto-generated if empty)
        summary: Session summary text
        decisions: List of decisions made in this session
        unresolved: List of unresolved items/questions
        project: Project name
        active_pipeline: Active pipeline folder path (e.g. '01_ideation/2026-03-11-task/')
    """
    _ready.wait()
    return _save_session(
        session_id=session_id,
        summary=summary,
        decisions=decisions,
        unresolved=unresolved,
        project=project,
        active_pipeline=active_pipeline,
    )


@mcp.tool()
def analyze_signals(
    domain: str = "",
    min_cluster_size: int = 2,
    top_k: int = 5,
) -> dict:
    """Analyze Signal-type nodes for promotion readiness.

    Clusters Signals by shared tags/concepts/domains and computes maturity scores.
    Maturity > 0.9: auto-promotable, 0.6-0.9: needs user review, < 0.6: not ready.

    Args:
        domain: Filter by domain (e.g. "orchestration")
        min_cluster_size: Minimum signals in a cluster (default 2)
        top_k: Maximum clusters to return (default 5)
    """
    _ready.wait()
    return _analyze_signals(
        domain=domain,
        min_cluster_size=min_cluster_size,
        top_k=top_k,
    )


@mcp.tool()
def promote_node(
    node_id: int,
    target_type: str,
    reason: str = "",
    related_ids: list[int] | None = None,
    skip_gates: bool = False,
    actor: str = "system",
) -> dict:
    """Promote a node to a higher-layer type (e.g. Signal → Pattern).

    Creates realized_as edges from related nodes and preserves promotion history.
    Valid paths: Observation→Signal/Evidence, Signal→Pattern/Insight,
    Pattern→Principle/Framework/Heuristic, Insight→Principle/Concept.

    Args:
        node_id: Node to promote
        target_type: Target type name
        reason: Why this promotion is justified
        related_ids: Other node IDs in the same cluster (creates realized_as edges)
        skip_gates: Skip 3-gate validation (SWR/Bayesian/MDL) for manual promotion
    """
    _ready.wait()
    # ── [접근 제어] promote 대상 노드 write 권한 확인 ────────────────────
    if not check_access(node_id, "write", actor):
        return {
            "error": f"Access denied: actor='{actor}' cannot promote node #{node_id}",
            "message": f"check_access denied 'write' on node #{node_id} for actor='{actor}'",
        }

    # skip_gates는 paul/claude만 허용 (보안 가드)
    effective_skip = skip_gates and actor in ("paul", "claude")

    return _promote_node(
        node_id=node_id,
        target_type=target_type,
        reason=reason,
        related_ids=related_ids,
        skip_gates=effective_skip,
    )


@mcp.tool()
def get_becoming(
    domain: str = "",
    top_k: int = 10,
) -> dict:
    """Show nodes that are growing toward promotion (Signal, Pattern, Observation).

    Returns maturity scores based on quality and connectivity.
    Use analyze_signals() for detailed cluster analysis.

    Args:
        domain: Filter by domain
        top_k: Maximum nodes to return (default 10)
    """
    _ready.wait()
    return _get_becoming(domain=domain, top_k=top_k)


@mcp.tool()
def flag_node(
    node_id: int,
    reason: str,
    action: str = "inaccurate",
) -> dict:
    """Flag a memory node as inaccurate, outdated, or irrelevant.

    Creates a Correction node, lowers confidence, and links with contradicts edge.
    Use this when recall returns wrong or misleading results.

    Args:
        node_id: The node ID to flag
        reason: Why this node is wrong (brief explanation)
        action: Flag type — "inaccurate" (factually wrong), "outdated" (no longer true), "irrelevant" (noise)
    """
    _ready.wait()
    return _flag_node(node_id=node_id, reason=reason, action=action)


@mcp.tool()
def visualize(
    center: str = "",
    depth: int = 2,
    max_nodes: int = 100,
) -> dict:
    """Generate an interactive HTML graph visualization of memory nodes.

    Opens in browser. Nodes colored by type, edges show relationships.

    Args:
        center: Search query for center node (empty = recent nodes)
        depth: Graph traversal depth from center (default 2)
        max_nodes: Maximum nodes to display (default 100)
    """
    _ready.wait()
    return _visualize(center=center, depth=depth, max_nodes=max_nodes)


@mcp.tool()
def ontology_review() -> str:
    """Run ontology health review: type distribution, unused types, orphan nodes, Unclassified analysis.

    Returns a markdown report and saves to data/ontology-review.md.
    """
    _ready.wait()
    return _ontology_review()


@mcp.tool()
def dashboard() -> dict:
    """Generate an interactive HTML dashboard with charts, graph visualization, and memory table.

    Returns the file path. Open in browser to view.
    """
    _ready.wait()
    path = _generate_dashboard()
    return {"file": path, "message": f"Dashboard generated: {path}"}


# ── v6.0 Session Events + Export ──────────────────────────


@mcp.tool()
def emit_event(
    event_id: str,
    session_id: str,
    event_type: str,
    summary: str,
    project: str = "",
    metadata: dict | None = None,
    target: str = "",
    task_id: str = "",
) -> dict:
    """Emit a session event (idempotent — duplicate event_id ignored).

    Event types: FILE_CONFLICT, DECISION_MADE, PIPELINE_ADVANCE,
    TASK_COMPLETE, HEALTH_ALERT, TASK_ASSIGN, TASK_PICK

    Args:
        event_id: Deterministic hash for idempotency
        session_id: Source session identifier
        event_type: Event category
        summary: Human-readable description
        project: Project name
        metadata: Additional context (JSON)
        target: Target agent for TASK_ASSIGN (codex/gemini/claude)
        task_id: Associated task ID from tasks.db
    """
    valid_types = {"FILE_CONFLICT", "DECISION_MADE", "PIPELINE_ADVANCE",
                   "TASK_COMPLETE", "HEALTH_ALERT", "TASK_ASSIGN", "TASK_PICK"}
    _ready.wait()
    if event_type not in valid_types:
        return {"error": f"Invalid event_type: {event_type}. Valid: {valid_types}"}
    return insert_session_event(event_id, session_id, event_type, summary, project, metadata, target, task_id)


@mcp.tool()
def resolve_event(event_id: str) -> dict:
    """Mark a session event as resolved.

    Args:
        event_id: The event to resolve
    """
    _ready.wait()
    ok = resolve_session_event(event_id)
    return {"resolved": ok, "event_id": event_id}


@mcp.tool()
def export_ontology(
    types: list[str] | None = None,
    project: str = "",
    since: str = "",
    changed_only: bool = False,
) -> dict:
    """Export full ontology (nodes + edges) as JSON for AI analysis.

    Used by weekly 3-way ontology scan (Claude + Codex + Gemini).
    ~500K tokens at current scale (4,200+ nodes).

    Args:
        types: Filter by node types (e.g. ["Decision", "Pattern"])
        project: Filter by project name
        since: ISO timestamp — nodes created/updated after this date
        changed_only: If True with 'since', use updated_at instead of created_at
    """
    _ready.wait()
    return _export_ontology(types, project, since, changed_only)


# ── v6.1: Beads (tasks.db) ────────────────────────────────────────

from storage.task_store import (
    create_task as _create_task,
    query_tasks as _query_tasks,
    complete_task as _complete_task,
    generate_next_section as _generate_next,
)


@mcp.tool()
def create_task(
    title: str,
    project: str = "",
    priority: int = 2,
    assigned_to: str = "claude",
    pipeline: str = "",
    phase: str = "",
    auto_eligible: int = 0,
    task_type: str = "llm_complex",
    blocked_by: str = "",
) -> dict:
    """Create a task in the Beads task graph (tasks.db).

    Args:
        title: Task description
        project: Project name (mcp-memory, orchestration, etc.)
        priority: 1=highest, 2=normal, 3=low
        assigned_to: Agent name (claude, codex, gemini)
        pipeline: Pipeline name (e.g. 15_agent-autonomy_0408)
        phase: Pipeline phase (e.g. build-r1)
        auto_eligible: 1 if Phase 4 auto-execution allowed
        task_type: script (Python $0) / llm_simple (Haiku) / llm_complex (Opus)
        blocked_by: Comma-separated task IDs that must complete first
    """
    return _create_task(title, project, priority, assigned_to,
                        pipeline, phase, auto_eligible, task_type, blocked_by)


@mcp.tool()
def query_tasks(
    project: str = "",
    status: str = "",
    assigned_to: str = "",
    pipeline: str = "",
    limit: int = 10,
) -> dict:
    """Query tasks from the Beads task graph.

    Args:
        project: Filter by project
        status: Filter by status (backlog/ready/in_progress/done/cancelled). Empty = ready+in_progress
        assigned_to: Filter by agent
        pipeline: Filter by pipeline
        limit: Max results (default 10)
    """
    tasks = _query_tasks(project, status, assigned_to, pipeline, limit)
    return {"tasks": tasks, "count": len(tasks)}


@mcp.tool()
def complete_task(
    task_id: str,
    result: str = "",
) -> dict:
    """Complete a task. Auto-resolves blocked_by dependencies.
    Emits TASK_COMPLETE SessionEvent for cross-session awareness.

    Args:
        task_id: Task ID to complete
        result: Result summary
    """
    import hashlib, os
    outcome = _complete_task(task_id, result)
    if "error" not in outcome:
        session_id = os.environ.get("CLAUDE_SESSION_ID", str(os.getpid()))
        event_id = hashlib.sha256(
            f"{session_id}:task_complete:{task_id}".encode()
        ).hexdigest()[:16]
        project = outcome.get("project", "")
        summary = f"Task {task_id} done: {result[:100]}" if result else f"Task {task_id} done"
        unblocked = outcome.get("unblocked", [])
        if unblocked:
            summary += f" → unblocked: {', '.join(u['title'] for u in unblocked)}"
        try:
            insert_session_event(event_id, session_id, "TASK_COMPLETE", summary, project)
        except Exception as e:
            import logging
            logging.warning(f"TASK_COMPLETE event emit failed for {task_id}: {e}")
    return outcome


@mcp.tool()
def generate_next(project: str = "") -> dict:
    """Generate STATE.md 'Next' section from tasks.db.

    Args:
        project: Filter by project. Empty = all projects.
    """
    md = _generate_next(project)
    return {"markdown": md}


if __name__ == "__main__":
    mcp.run(transport="stdio")

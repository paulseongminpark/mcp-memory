"""MCP Memory Server — 3중 하이브리드 검색 외부 메모리."""

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP

from config import DB_PATH, OPENAI_API_KEY
from storage.sqlite_store import init_db

if not OPENAI_API_KEY:
    import warnings
    warnings.warn("OPENAI_API_KEY not set — embedding features will fail")
from tools.remember import remember as _remember
from tools.recall import recall as _recall
from tools.get_context import get_context as _get_context
from tools.save_session import save_session as _save_session
from tools.suggest_type import suggest_type as _suggest_type
from tools.visualize import visualize as _visualize
from tools.analyze_signals import analyze_signals as _analyze_signals
from tools.promote_node import promote_node as _promote_node
from tools.get_becoming import get_becoming as _get_becoming
from tools.inspect_node import inspect_node as _inspect_node
from ingestion.obsidian import ingest_vault as _ingest_vault
from scripts.ontology_review import run_review as _ontology_review
from scripts.dashboard import generate_dashboard as _generate_dashboard

mcp = FastMCP(
    "memory",
    instructions="External memory system with hybrid search (Vector + FTS5 + Graph). "
    "Use remember() to store, recall() to search, get_context() for session summary.",
)


@mcp.tool()
def remember(
    content: str,
    type: str = "Unclassified",
    tags: str = "",
    project: str = "",
    metadata: dict | None = None,
    confidence: float = 1.0,
    source: str = "claude",
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
    """
    return _remember(
        content=content,
        type=type,
        tags=tags,
        project=project,
        metadata=metadata,
        confidence=confidence,
        source=source,
    )


@mcp.tool()
def recall(
    query: str,
    type_filter: str = "",
    project: str = "",
    top_k: int = 5,
) -> dict:
    """Search memories using 3-way hybrid search (Vector + FTS5 + Graph).

    Returns up to top_k results ranked by Reciprocal Rank Fusion,
    with relationship paths and content previews.

    Args:
        query: Search query (natural language or keywords)
        type_filter: Filter by node type (e.g. "Decision", "Pattern")
        project: Filter by project name
        top_k: Number of results to return (default 5)
    """
    return _recall(
        query=query,
        type_filter=type_filter,
        project=project,
        top_k=top_k,
    )


@mcp.tool()
def get_context(project: str = "") -> dict:
    """Get a compact context summary (~200 tokens) for session start.

    Returns recent decisions, open questions, insights, and failures.

    Args:
        project: Filter by project name (empty = all projects)
    """
    return _get_context(project=project)


@mcp.tool()
def save_session(
    session_id: str = "",
    summary: str = "",
    decisions: list[str] | None = None,
    unresolved: list[str] | None = None,
    project: str = "",
) -> dict:
    """Save structured session data (summary, decisions, unresolved items).

    Args:
        session_id: Unique session identifier (auto-generated if empty)
        summary: Session summary text
        decisions: List of decisions made in this session
        unresolved: List of unresolved items/questions
        project: Project name
    """
    return _save_session(
        session_id=session_id,
        summary=summary,
        decisions=decisions,
        unresolved=unresolved,
        project=project,
    )


@mcp.tool()
def suggest_type(
    content: str,
    reason: str = "",
    attempted_type: str = "",
    tags: str = "",
    project: str = "",
) -> dict:
    """Store as Unclassified when no existing type fits, and queue for review.

    Use when a memory doesn't fit any of the 26 node types.
    3+ similar Unclassified → automatic suggestion for new type.

    Args:
        content: The memory content
        reason: Why existing types don't fit
        attempted_type: What type was tried
        tags: Comma-separated tags
        project: Project name
    """
    return _suggest_type(
        content=content,
        reason=reason,
        attempted_type=attempted_type,
        tags=tags,
        project=project,
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
    """
    return _promote_node(
        node_id=node_id,
        target_type=target_type,
        reason=reason,
        related_ids=related_ids,
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
    return _get_becoming(domain=domain, top_k=top_k)


@mcp.tool()
def inspect(node_id: int) -> dict:
    """Get full detail of a memory node: all metadata, edges, enrichment status, promotion history.

    Args:
        node_id: The node ID to inspect
    """
    return _inspect_node(node_id=node_id)


@mcp.tool()
def ingest_obsidian(
    vault_path: str = "/c/dev/",
    force: bool = False,
    max_files: int = 0,
) -> dict:
    """Ingest Obsidian vault markdown files into memory.

    Chunks by ## headings, embeds, and stores. Incremental by default
    (skips already-ingested files unless force=True).

    Args:
        vault_path: Vault root path (default /c/dev/)
        force: Re-process already ingested files
        max_files: Limit number of files (0 = all)
    """
    return _ingest_vault(vault_path=vault_path, force=force, max_files=max_files)


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
    return _visualize(center=center, depth=depth, max_nodes=max_nodes)


@mcp.tool()
def ontology_review() -> str:
    """Run ontology health review: type distribution, unused types, orphan nodes, Unclassified analysis.

    Returns a markdown report and saves to data/ontology-review.md.
    """
    return _ontology_review()


@mcp.tool()
def dashboard() -> dict:
    """Generate an interactive HTML dashboard with charts, graph visualization, and memory table.

    Returns the file path. Open in browser to view.
    """
    path = _generate_dashboard()
    return {"file": path, "message": f"Dashboard generated: {path}"}


# DB 초기화
init_db()

if __name__ == "__main__":
    mcp.run(transport="stdio")

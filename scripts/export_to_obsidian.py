"""
export_to_obsidian.py
mcp-memory DB → /c/dev/04_memory_export/ 마크다운 export
실행: python scripts/export_to_obsidian.py
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# 경로 설정
DB_PATH = Path("C:/dev/01_projects/06_mcp-memory/data/memory.db")
EXPORT_ROOT = Path("C:/dev/04_memory_export")
TODAY = datetime.now().strftime("%Y-%m-%d")
CUTOFF_30D = (datetime.now() - timedelta(days=30)).isoformat()

# 각 파일별 (상대경로, 헤더타이틀, SQL쿼리)
EXPORTS = [
    (
        "00_core/values.md",
        "VALUES",
        "SELECT * FROM nodes WHERE type IN ('Value','Belief') AND status='active'"
        " ORDER BY quality_score DESC NULLS LAST",
    ),
    (
        "00_core/principles.md",
        "PRINCIPLES",
        "SELECT * FROM nodes WHERE type IN ('Principle','Heuristic') AND status='active'"
        " ORDER BY quality_score DESC NULLS LAST",
    ),
    (
        "00_core/worldview.md",
        "WORLDVIEW",
        "SELECT * FROM nodes WHERE type IN ('Framework','Concept') AND status='active'"
        " ORDER BY quality_score DESC NULLS LAST",
    ),
    (
        "01_patterns/insights.md",
        "INSIGHTS",
        "SELECT * FROM nodes WHERE type='Insight' AND status='active'"
        " ORDER BY quality_score DESC NULLS LAST",
    ),
    (
        "01_patterns/patterns.md",
        "PATTERNS",
        "SELECT * FROM nodes WHERE type='Pattern' AND status='active'"
        " ORDER BY quality_score DESC NULLS LAST",
    ),
    (
        "01_patterns/frameworks.md",
        "FRAMEWORKS",
        "SELECT * FROM nodes WHERE type IN ('Framework','Heuristic') AND status='active'"
        " ORDER BY quality_score DESC NULLS LAST",
    ),
    (
        "02_log/decisions.md",
        "DECISIONS",
        "SELECT * FROM nodes WHERE type='Decision' AND status='active'"
        " AND created_at >= '{cutoff_30d}' ORDER BY created_at DESC",
    ),
    (
        "02_log/failures.md",
        "FAILURES",
        "SELECT * FROM nodes WHERE type='Failure' AND status='active'"
        " AND created_at >= '{cutoff_30d}' ORDER BY created_at DESC",
    ),
    (
        "02_log/breakthroughs.md",
        "BREAKTHROUGHS",
        "SELECT * FROM nodes WHERE type='Breakthrough' AND status='active'"
        " AND created_at >= '{cutoff_30d}' ORDER BY created_at DESC",
    ),
]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fmt_node(row) -> str:
    """노드 하나를 md 블록으로 포맷 (요청 스펙 준수)"""
    content = (row["content"] or "").strip()
    summary = (row["summary"] or "").strip()
    tags = (row["tags"] or "").strip()
    node_type = row["type"] or ""
    quality = row["quality_score"]
    layer = row["layer"]
    created = (row["created_at"] or "")[:10]

    # 제목: 첫 줄 최대 60자
    first_line = content.split("\n")[0][:60]
    if len(content.split("\n")[0]) > 60:
        first_line += "…"

    lines = [f"## [{node_type}] {first_line}", ""]

    if summary:
        lines.append(f"**요약:** {summary}")
    if tags:
        lines.append(f"**태그:** {tags}")

    quality_str = f"{quality:.2f}" if quality is not None else "N/A"
    layer_str = str(layer) if layer is not None else "N/A"
    lines.append(f"**품질:** {quality_str} | **레이어:** {layer_str}")
    lines.append(f"**날짜:** {created}")
    lines.append("")

    # 본문 최대 500자
    body = content[:500]
    if len(content) > 500:
        body += "…"
    lines.append(body)
    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def export_file(
    conn: sqlite3.Connection,
    path: Path,
    title: str,
    query: str,
    cutoff_30d: str,
) -> int:
    """쿼리 실행 → md 파일 작성. 작성된 행 수 반환."""
    rows = conn.execute(query.format(cutoff_30d=cutoff_30d)).fetchall()

    path.parent.mkdir(parents=True, exist_ok=True)

    header_lines = [
        "---",
        f"updated: {TODAY}",
        "source: mcp-memory",
        "---",
        "",
        f"# {title}",
        f"생성: {TODAY}",
        f"총 {len(rows)}건",
        "",
    ]

    node_blocks = [fmt_node(r) for r in rows]

    content = "\n".join(header_lines) + "\n".join(node_blocks)
    path.write_text(content, encoding="utf-8")

    print(f"  {path.relative_to(EXPORT_ROOT)}  ({len(rows)}건)")
    return len(rows)


def main():
    print(f"[{TODAY}] mcp-memory → 04_memory_export export 시작")
    print(f"  DB: {DB_PATH}")
    print(f"  EXPORT_ROOT: {EXPORT_ROOT}")
    print()

    conn = get_conn()
    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)

    total = 0
    try:
        for subpath, title, query in EXPORTS:
            count = export_file(conn, EXPORT_ROOT / subpath, title, query, CUTOFF_30D)
            total += count
    finally:
        conn.close()

    print()
    print(f"Export 완료: {EXPORT_ROOT}  (총 {total}건)")


if __name__ == "__main__":
    main()

"""save_session() — 세션 구조화 저장."""

import json
from datetime import datetime, timezone

from storage import sqlite_store


def save_session(
    session_id: str = "",
    summary: str = "",
    decisions: list[str] | None = None,
    unresolved: list[str] | None = None,
    project: str = "",
) -> dict:
    if not session_id:
        session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    now = datetime.now(timezone.utc).isoformat()
    with sqlite_store._db() as conn:
        # UPSERT: 이미 있으면 업데이트
        conn.execute(
            """INSERT INTO sessions (session_id, summary, decisions, unresolved, project, started_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                 summary = excluded.summary,
                 decisions = excluded.decisions,
                 unresolved = excluded.unresolved,
                 ended_at = ?""",
            (
                session_id,
                summary,
                json.dumps(decisions or [], ensure_ascii=False),
                json.dumps(unresolved or [], ensure_ascii=False),
                project,
                now,
                now,
            ),
        )
        conn.commit()

    return {
        "session_id": session_id,
        "summary": summary[:100],
        "decisions_count": len(decisions or []),
        "unresolved_count": len(unresolved or []),
        "message": f"Session '{session_id}' saved",
    }

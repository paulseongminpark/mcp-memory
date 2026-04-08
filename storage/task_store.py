"""v6.1 Beads — tasks.db 태스크 그래프 관리.

별도 SQLite 파일(tasks.db)로 memory.db와 락 격리.
DAG 의존성(task_deps)으로 blocked_by 자동 해소.
"""

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from config import TASKS_DB_PATH


def _connect() -> sqlite3.Connection:
    TASKS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(TASKS_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def _db():
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


def init_tasks_db():
    """tasks.db 스키마 초기화."""
    with _db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                project     TEXT DEFAULT '',
                status      TEXT DEFAULT 'backlog',
                priority    INTEGER DEFAULT 2,
                assigned_to TEXT DEFAULT 'claude',
                pipeline    TEXT DEFAULT '',
                phase       TEXT DEFAULT '',
                auto_eligible INTEGER DEFAULT 0,
                task_type   TEXT DEFAULT 'llm_complex',
                result      TEXT DEFAULT '',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS task_deps (
                task_id     TEXT NOT NULL REFERENCES tasks(id),
                blocked_by  TEXT NOT NULL REFERENCES tasks(id),
                PRIMARY KEY (task_id, blocked_by)
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project);
            CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
            CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON tasks(assigned_to);
        """)
        conn.commit()


def _resolve_status(conn: sqlite3.Connection, task_id: str) -> str:
    """blocked_by가 모두 done이면 'ready', 아니면 'backlog'."""
    blockers = conn.execute(
        "SELECT t.status FROM task_deps d JOIN tasks t ON t.id = d.blocked_by WHERE d.task_id = ?",
        (task_id,),
    ).fetchall()
    if not blockers:
        return "ready"
    return "ready" if all(r["status"] == "done" for r in blockers) else "backlog"


def _update_dependents(conn: sqlite3.Connection, completed_task_id: str):
    """완료된 태스크를 blocked_by로 가진 태스크들의 상태 갱신."""
    now = datetime.now(timezone.utc).isoformat()
    dependents = conn.execute(
        "SELECT DISTINCT task_id FROM task_deps WHERE blocked_by = ?",
        (completed_task_id,),
    ).fetchall()
    for row in dependents:
        tid = row["task_id"]
        current = conn.execute("SELECT status FROM tasks WHERE id = ?", (tid,)).fetchone()
        if current and current["status"] == "backlog":
            new_status = _resolve_status(conn, tid)
            if new_status == "ready":
                conn.execute(
                    "UPDATE tasks SET status = 'ready', updated_at = ? WHERE id = ?",
                    (now, tid),
                )


def _has_cycle(conn: sqlite3.Connection, task_id: str, new_dep: str) -> bool:
    """new_dep → ... → task_id 경로가 있으면 순환."""
    visited: set[str] = set()
    stack = [task_id]
    while stack:
        current = stack.pop()
        if current == new_dep:
            return True
        if current in visited:
            continue
        visited.add(current)
        rows = conn.execute(
            "SELECT task_id FROM task_deps WHERE blocked_by = ?", (current,)
        ).fetchall()
        stack.extend(r["task_id"] for r in rows)
    return False


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
    """태스크 생성. blocked_by = 쉼표 구분 task_id 목록."""
    task_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()

    with _db() as conn:
        conn.execute(
            """INSERT INTO tasks (id, title, project, priority, assigned_to,
               pipeline, phase, auto_eligible, task_type, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, title, project, priority, assigned_to,
             pipeline, phase, auto_eligible, task_type, now, now),
        )

        if blocked_by:
            for dep_id in [b.strip() for b in blocked_by.split(",") if b.strip()]:
                if not conn.execute("SELECT 1 FROM tasks WHERE id = ?", (dep_id,)).fetchone():
                    conn.rollback()
                    return {"error": f"Dependency {dep_id} not found"}
                if _has_cycle(conn, task_id, dep_id):
                    conn.rollback()
                    return {"error": f"Cycle detected: {dep_id} → ... → {task_id}"}
                conn.execute(
                    "INSERT INTO task_deps (task_id, blocked_by) VALUES (?, ?)",
                    (task_id, dep_id),
                )

        status = _resolve_status(conn, task_id)
        conn.execute(
            "UPDATE tasks SET status = ? WHERE id = ?", (status, task_id)
        )
        conn.commit()

    return {"task_id": task_id, "status": status, "title": title}


def query_tasks(
    project: str = "",
    status: str = "",
    assigned_to: str = "",
    pipeline: str = "",
    limit: int = 10,
) -> list[dict]:
    """태스크 조회. status 미지정 시 ready+in_progress."""
    conditions = []
    params: list = []

    if status:
        conditions.append("status = ?")
        params.append(status)
    else:
        conditions.append("status IN ('ready', 'in_progress')")

    if project:
        conditions.append("project = ?")
        params.append(project)
    if assigned_to:
        conditions.append("assigned_to = ?")
        params.append(assigned_to)
    if pipeline:
        conditions.append("pipeline = ?")
        params.append(pipeline)

    params.append(limit)
    where = " AND ".join(conditions) if conditions else "1=1"

    with _db() as conn:
        rows = conn.execute(
            f"SELECT * FROM tasks WHERE {where} ORDER BY priority ASC, created_at ASC LIMIT ?",
            params,
        ).fetchall()

        result = []
        for r in rows:
            task = dict(r)
            deps = conn.execute(
                "SELECT blocked_by FROM task_deps WHERE task_id = ?", (task["id"],)
            ).fetchall()
            task["blocked_by"] = [d["blocked_by"] for d in deps]
            result.append(task)

        return result


def complete_task(task_id: str, result: str = "") -> dict:
    """태스크 완료. blocked_by 자동 해소."""
    now = datetime.now(timezone.utc).isoformat()

    with _db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return {"error": f"Task {task_id} not found"}

        conn.execute(
            "UPDATE tasks SET status = 'done', result = ?, updated_at = ? WHERE id = ?",
            (result, now, task_id),
        )
        _update_dependents(conn, task_id)
        conn.commit()

        # 새로 ready된 태스크 목록
        unblocked = conn.execute(
            """SELECT t.id, t.title FROM tasks t
               JOIN task_deps d ON t.id = d.task_id
               WHERE d.blocked_by = ? AND t.status = 'ready'""",
            (task_id,),
        ).fetchall()

    return {
        "task_id": task_id,
        "status": "done",
        "result": result,
        "project": row["project"],
        "unblocked": [{"id": u["id"], "title": u["title"]} for u in unblocked],
    }


def generate_next_section(project: str = "") -> str:
    """tasks.db에서 프로젝트별 미완료 태스크를 STATE.md "Next" 마크다운으로 생성."""
    with _db() as conn:
        conditions = ["status IN ('ready', 'in_progress', 'backlog')"]
        params: list = []
        if project:
            conditions.append("project = ?")
            params.append(project)
        where = " AND ".join(conditions)

        rows = conn.execute(
            f"""SELECT id, title, status, priority, assigned_to, project
                FROM tasks WHERE {where}
                ORDER BY priority ASC, status DESC, created_at ASC""",
            params,
        ).fetchall()

    if not rows:
        return ""

    lines = ["## Next (auto-generated from tasks.db)", ""]
    for r in rows:
        icon = {"ready": "🟢", "in_progress": "🔄", "backlog": "⬜"}.get(r["status"], "⬜")
        check = "[x]" if r["status"] == "in_progress" else "[ ]"
        proj = f"[{r['project']}] " if r["project"] and not project else ""
        lines.append(f"- {check} {icon} {proj}{r['title']}")

    return "\n".join(lines) + "\n"


# 초기화
init_tasks_db()

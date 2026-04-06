"""Obsidian vault ingestion — vault 순회 → 청크 → 임베딩 → 저장."""

import os
import hashlib
from pathlib import Path

from ingestion.chunker import chunk_markdown
from storage import sqlite_store, vector_store

# 제외 패턴
EXCLUDE_DIRS = {
    ".git", "node_modules", "dist", "build", ".next", ".cache",
    "__pycache__", ".obsidian", ".trash", "data", "chroma",
    ".ctx", "worktrees", ".chain-temp",
    # vault-specific
    "99_archive", "03_llm",
}

EXCLUDE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".mp3", ".mp4", ".wav", ".pdf", ".zip", ".tar", ".gz",
    ".exe", ".dll", ".so", ".pyc", ".pyo", ".woff", ".woff2",
    ".ttf", ".eot", ".db", ".sqlite", ".lock", ".log",
}

# 포함할 확장자 (마크다운 위주)
INCLUDE_EXTENSIONS = {".md"}


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _should_skip(path: Path) -> bool:
    parts = path.parts
    for part in parts:
        if part in EXCLUDE_DIRS:
            return True
    if path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return True
    if path.suffix.lower() not in INCLUDE_EXTENSIONS:
        return True
    return False


def _resolve_path(p: str) -> Path:
    """MSYS 경로 (/c/dev/) → Windows 경로 (C:\\dev\\) 변환."""
    import re
    m = re.match(r"^/([a-zA-Z])/(.*)$", p)
    if m:
        return Path(f"{m.group(1).upper()}:/{m.group(2)}")
    return Path(p)


def ingest_vault(
    vault_path: str = "/c/dev/",
    force: bool = False,
    max_files: int = 0,
) -> dict:
    """Obsidian vault 전체를 ingestion.

    Args:
        vault_path: Vault 루트 경로
        force: True면 이미 저장된 파일도 재처리
        max_files: 0이면 전체, 양수면 최대 파일 수 제한

    Returns:
        {"files_processed": int, "chunks_created": int, "skipped": int, "errors": list}
    """
    vault = _resolve_path(vault_path)
    if not vault.exists():
        return {"error": f"Vault path not found: {vault_path}"}

    # 이미 ingestion된 파일 해시 조회 (증분용)
    existing_hashes = set()
    if not force:
        existing = sqlite_store.get_recent_nodes(limit=10000, type_filter="")
        for n in existing:
            if n.get("source", "").startswith("obsidian:"):
                # source = "obsidian:/path/to/file.md#hash"
                parts = n["source"].split("#")
                if len(parts) > 1:
                    existing_hashes.add(parts[-1])

    stats = {"files_processed": 0, "chunks_created": 0, "skipped": 0, "errors": []}
    file_count = 0

    for root, dirs, files in os.walk(vault):
        # 제외 디렉토리 prune
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for fname in sorted(files):
            fpath = Path(root) / fname
            if _should_skip(fpath):
                continue

            if max_files > 0 and file_count >= max_files:
                break

            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                stats["errors"].append(f"{fpath}: {e}")
                continue

            if not text.strip():
                continue

            # 해시 기반 증분 체크
            file_hash = _content_hash(text)
            if file_hash in existing_hashes:
                stats["skipped"] += 1
                continue

            rel_path = str(fpath.relative_to(vault))
            chunks = chunk_markdown(text, source_path=rel_path)

            # 프로젝트 추정 (경로 기반)
            project = _guess_project(rel_path)
            chunk_ids = []  # 같은 파일 chunk간 edge 생성용

            for chunk in chunks:
                content = chunk["content"]
                if len(content.strip()) < 20:
                    continue

                node_id = sqlite_store.insert_node(
                    type="Conversation",  # Obsidian 노트는 Conversation 타입
                    content=content,
                    metadata={"heading": chunk["heading"], "file": rel_path},
                    project=project,
                    tags=f"obsidian,{Path(rel_path).stem}",
                    source=f"obsidian:{rel_path}#{file_hash}",
                )
                chunk_ids.append(node_id)

                try:
                    vec_meta = {
                        "type": "Conversation",
                        "project": project,
                        "source": f"obsidian:{rel_path}",
                    }
                    vector_store.add(node_id, content, vec_meta)
                except Exception as e:
                    stats["errors"].append(f"Embedding failed for {rel_path}: {e}")

                stats["chunks_created"] += 1

            # 같은 파일 chunk끼리 part_of edge 생성 (orphan 방지)
            if len(chunk_ids) >= 2:
                anchor = chunk_ids[0]
                for cid in chunk_ids[1:]:
                    try:
                        sqlite_store.insert_edge(
                            source_id=cid,
                            target_id=anchor,
                            relation="part_of",
                            description=f"same file: {rel_path}",
                            strength=0.7,
                        )
                    except Exception:
                        pass  # 중복 등 무시

            stats["files_processed"] += 1
            file_count += 1

        if max_files > 0 and file_count >= max_files:
            break

    stats["message"] = (
        f"Ingested {stats['files_processed']} files, "
        f"{stats['chunks_created']} chunks, "
        f"{stats['skipped']} skipped"
    )
    return stats


def _guess_project(rel_path: str) -> str:
    """경로에서 프로젝트 이름 추정."""
    lower = rel_path.lower()
    if "01_orchestration" in lower or "orchestration" in lower:
        return "orchestration"
    if "02_portfolio" in lower or "portfolio" in lower:
        return "portfolio"
    if "03_tech-review" in lower or "tech-review" in lower:
        return "tech-review"
    if "04_monet-lab" in lower or "monet-lab" in lower:
        return "monet-lab"
    if "mcp-memory" in lower:
        return "mcp-memory"
    return ""

"""Shared embed text builder for embedding-friendly node text."""

from __future__ import annotations

import json


def _normalize_text(value: object) -> str:
    """Convert text or JSON-ish list payloads into a compact embedding string."""
    if value is None:
        return ""
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, TypeError, ValueError):
                return text
            if isinstance(parsed, list):
                return ", ".join(str(item).strip() for item in parsed if str(item).strip())
        return text
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def build_embed_text(
    content: str,
    summary: str = "",
    key_concepts: str = "",
    retrieval_queries: str = "",
    node_type: str = "",
    project: str = "",
) -> str:
    """Build structured embed text from node content and enrichment fields."""
    parts: list[str] = []

    header_parts = [part for part in (node_type.strip(), project.strip()) if part]
    if header_parts:
        parts.append(f"[{' | '.join(header_parts)}]")

    body = _normalize_text(summary)
    raw_content = _normalize_text(content)
    if body:
        parts.append(body)
        if raw_content and len(raw_content) > len(body) * 2:
            parts.append(raw_content[:200].strip())
    elif raw_content:
        parts.append(raw_content)

    keywords = _normalize_text(key_concepts)
    if keywords:
        parts.append(f"Keywords: {keywords}")

    queries = _normalize_text(retrieval_queries)
    if queries:
        parts.append(f"Queries: {queries}")

    return "\n".join(parts)

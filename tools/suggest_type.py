"""suggest_type() — Unclassified 저장 + 새 타입 제안 큐."""

from tools.remember import remember


def suggest_type(
    content: str,
    reason: str = "",
    attempted_type: str = "",
    tags: str = "",
    project: str = "",
) -> dict:
    """분류 불가 시 Unclassified로 저장 + 새 타입 제안 기록."""
    metadata = {
        "attempted_type": attempted_type,
        "reason_failed": reason,
    }

    result = remember(
        content=content,
        type="Unclassified",
        tags=f"unclassified,needs-review,{tags}".strip(","),
        project=project,
        metadata=metadata,
    )

    result["suggestion"] = {
        "attempted_type": attempted_type,
        "reason": reason,
        "action": "Review Unclassified nodes periodically. 3+ similar → propose new type.",
    }
    return result

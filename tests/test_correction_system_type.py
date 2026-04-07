from __future__ import annotations

from ontology.validators import validate_node_type
from storage import sqlite_store


def test_correction_is_valid_even_if_type_defs_marks_deprecated(fresh_db):
    with sqlite_store._db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO type_defs
            (name, status, replaced_by, description, layer, super_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                "Correction",
                "deprecated",
                "Insight",
                "system type",
                None,
                None,
            ),
        )
        conn.commit()

    assert validate_node_type("Correction") == (True, None)
    assert validate_node_type("correction") == (True, "Correction")

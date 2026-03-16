"""Tests for v6.0 Session Events (Event Journal)."""
import hashlib
from datetime import datetime, timezone

from storage.sqlite_store import (
    insert_session_event,
    query_session_events,
    resolve_session_event,
    export_ontology,
)


def _make_event_id(session_id: str, suffix: str) -> str:
    return hashlib.sha256(f"{session_id}:{suffix}".encode()).hexdigest()[:16]


def test_insert_and_query(fresh_db):
    eid = _make_event_id("sess-A", "test1")
    result = insert_session_event(
        event_id=eid,
        session_id="sess-A",
        event_type="HEALTH_ALERT",
        summary="portfolio site down",
        project="orchestration",
    )
    assert result["status"] == "created"
    assert result["event_id"] == eid

    events = query_session_events()
    assert len(events) == 1
    assert events[0]["event_type"] == "HEALTH_ALERT"
    assert events[0]["status"] == "ACTIVE"


def test_idempotent_insert(fresh_db):
    eid = _make_event_id("sess-A", "dup")
    insert_session_event(eid, "sess-A", "TASK_COMPLETE", "task done")
    result2 = insert_session_event(eid, "sess-A", "TASK_COMPLETE", "task done again")
    # second insert should be ignored (OR IGNORE)
    events = query_session_events()
    assert len(events) == 1
    assert events[0]["summary"] == "task done"


def test_exclude_session(fresh_db):
    insert_session_event(_make_event_id("A", "1"), "sess-A", "DECISION_MADE", "decision A")
    insert_session_event(_make_event_id("B", "1"), "sess-B", "DECISION_MADE", "decision B")

    events_excl_a = query_session_events(exclude_session="sess-A")
    assert len(events_excl_a) == 1
    assert events_excl_a[0]["session_id"] == "sess-B"


def test_since_filter(fresh_db):
    insert_session_event(_make_event_id("A", "old"), "sess-A", "HEALTH_ALERT", "old event")
    # query with a future timestamp should return nothing
    future = "2099-01-01T00:00:00"
    events = query_session_events(since=future)
    assert len(events) == 0

    # query with a past timestamp should return the event
    past = "2000-01-01T00:00:00"
    events = query_session_events(since=past)
    assert len(events) == 1


def test_resolve_event(fresh_db):
    eid = _make_event_id("A", "resolve")
    insert_session_event(eid, "sess-A", "FILE_CONFLICT", "conflict!")

    ok = resolve_session_event(eid)
    assert ok is True

    events = query_session_events(status="ACTIVE")
    assert len(events) == 0

    events = query_session_events(status="RESOLVED")
    assert len(events) == 1
    assert events[0]["resolved_at"] is not None


def test_resolve_nonexistent(fresh_db):
    ok = resolve_session_event("nonexistent-id")
    assert ok is False


def test_export_ontology_basic(fresh_db, sample_nodes, sample_edges):
    result = export_ontology()
    assert result["meta"]["nodes"] == 3
    assert result["meta"]["edges"] == 2
    assert len(result["nodes"]) == 3
    assert len(result["edges"]) == 2


def test_export_ontology_type_filter(fresh_db, sample_nodes):
    result = export_ontology(types=["Observation"])
    assert result["meta"]["nodes"] == 1
    assert all(n["type"] == "Observation" for n in result["nodes"])


def test_export_ontology_project_filter(fresh_db, sample_nodes):
    result = export_ontology(project="")
    assert result["meta"]["nodes"] == 3  # sample_nodes have empty project


def test_multiple_event_types(fresh_db):
    types = ["FILE_CONFLICT", "DECISION_MADE", "PIPELINE_ADVANCE", "TASK_COMPLETE", "HEALTH_ALERT"]
    for i, t in enumerate(types):
        insert_session_event(_make_event_id("A", str(i)), "sess-A", t, f"event {t}")

    events = query_session_events()
    assert len(events) == 5
    event_types = {e["event_type"] for e in events}
    assert event_types == set(types)

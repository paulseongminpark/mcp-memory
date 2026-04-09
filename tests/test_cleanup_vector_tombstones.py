import sqlite3

from scripts.cleanup_vector_tombstones import apply_delete, collect_tombstones


class FakeCollection:
    def __init__(self, ids):
        self.ids = list(ids)
        self.deleted_batches = []

    def get(self, include=None):
        return {"ids": list(self.ids)}

    def delete(self, ids):
        self.deleted_batches.append(list(ids))
        doomed = set(ids)
        self.ids = [node_id for node_id in self.ids if node_id not in doomed]


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE nodes (id INTEGER PRIMARY KEY, status TEXT NOT NULL)")
    conn.executemany(
        "INSERT INTO nodes (id, status) VALUES (?, ?)",
        [(1, "active"), (2, "active"), (3, "archived"), (4, "active"), (5, "archived")],
    )
    conn.commit()
    return conn


def test_collect_tombstones_finds_stale_and_missing_ids():
    conn = _make_conn()
    coll = FakeCollection(["1", "2", "3", "5", "8"])
    try:
        result = collect_tombstones(conn, coll, sample_limit=5)
    finally:
        conn.close()

    assert result["active_count"] == 3
    assert result["collection_count"] == 5
    assert result["stale_count"] == 3
    assert result["missing_count"] == 1
    assert result["stale_sample"] == ["3", "5", "8"]
    assert result["missing_sample"] == ["4"]


def test_apply_delete_batches_stale_ids():
    coll = FakeCollection(["1", "2", "3", "4", "5"])
    result = apply_delete(coll, ["2", "4", "5"], batch_size=2)

    assert result == {"deleted_count": 3, "batch_size": 2}
    assert coll.deleted_batches == [["2", "4"], ["5"]]
    assert coll.ids == ["1", "3"]

from geoagent.store import Store


def test_conversation_turn_roundtrip(tmp_path):
    store = Store(tmp_path / "agent.db")
    conv = store.create_conversation("test")
    store.add_turn(conv, "user", "سلام")
    store.add_turn(conv, "assistant", "hello [S1]")
    turns = store.turns(conv)
    assert [t["role"] for t in turns] == ["user", "assistant"]
    assert turns[0]["content"] == "سلام"
    convs = store.list_conversations()
    assert convs[0]["id"] == conv


def test_tool_run_persisted(tmp_path):
    store = Store(tmp_path / "agent.db")
    conv = store.create_conversation("c")
    rid = store.record_tool_run(
        conversation_id=conv,
        turn_id=None,
        tool="geo_search",
        args={"query": "ndvi"},
        args_hash="abc",
        status="ok",
        latency_ms=12,
        error=None,
        artifacts=[{"path": "x.tif", "sha256": "ff"}],
        from_cache=False,
    )
    row = store.conn.execute("SELECT * FROM tool_run WHERE id=?", (rid,)).fetchone()
    assert row["tool"] == "geo_search" and row["latency_ms"] == 12

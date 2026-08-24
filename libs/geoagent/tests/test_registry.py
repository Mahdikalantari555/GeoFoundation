import time

from geoagent.registry import Registry, RunContext, ToolDefinition
from geoagent.store import Store


def make_ctx(tmp_path, max_tool_calls=8):
    store = Store(tmp_path / "agent.db")
    return RunContext(
        store=store,
        workspace_dir=tmp_path,
        sandbox_roots=[tmp_path],
        settings=None,
        max_tool_calls=max_tool_calls,
        deadline=time.monotonic() + 30,
    )


def test_validation_error_on_bad_args(tmp_path):
    reg = Registry()

    @reg.register(
        ToolDefinition(
            name="add",
            description="add",
            params={
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
                "additionalProperties": False,
            },
        )
    )
    def add(args, ctx):
        return args["a"] + args["b"]

    ctx = make_ctx(tmp_path)
    res = reg.call("add", {"a": 1}, ctx)
    assert res.status == "validation_error"
    assert "required" in res.error


def test_unknown_tool_and_audit_row(tmp_path):
    reg = Registry()
    ctx = make_ctx(tmp_path)
    res = reg.call("nope", {}, ctx)
    assert res.status == "validation_error"
    rows = ctx.store.conn.execute("SELECT * FROM tool_run").fetchall()
    assert rows[0]["tool"] == "nope"


def test_sandbox_escape_rejected(tmp_path):
    reg = Registry()

    @reg.register(
        ToolDefinition(name="read_it", description="r", params={"type": "object", "properties": {"input_path": {"type": "string"}}})
    )
    def read_it(args, ctx):
        return open(args["input_path"]).read()

    ctx = make_ctx(tmp_path)
    res = reg.call("read_it", {"input_path": "/etc/passwd"}, ctx)
    assert res.status == "validation_error"
    assert "sandbox" in res.error


def test_cacheable_hit(tmp_path):
    reg = Registry()
    calls = []

    @reg.register(ToolDefinition(name="calc", description="c", cacheable=True))
    def calc(args, ctx):
        calls.append(args)
        return {"n": args["x"] * 2}

    ctx = make_ctx(tmp_path)
    first = reg.call("calc", {"x": 21}, ctx)
    second = reg.call("calc", {"x": 21}, ctx)
    assert first.from_cache is False
    assert second.from_cache is True
    assert second.value == {"n": 42}
    assert len(calls) == 1


def test_budget_refused(tmp_path):
    reg = Registry()

    @reg.register(ToolDefinition(name="t1", description="t"))
    def t1(args, ctx):
        return 1

    ctx = make_ctx(tmp_path, max_tool_calls=1)
    assert reg.call("t1", {}, ctx).status == "ok"
    res = reg.call("t1", {}, ctx)
    assert res.status == "budget_refused"


def test_timeout_status(tmp_path):
    reg = Registry()

    @reg.register(ToolDefinition(name="slow", description="s", timeout_s=0.2))
    def slow(args, ctx):
        time.sleep(1.0)
        return "done"

    ctx = make_ctx(tmp_path)
    res = reg.call("slow", {}, ctx)
    assert res.status == "timeout"

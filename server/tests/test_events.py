from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any

import geofront_api.events as events_mod
import httpx
from geofront_api.events import EventBus, get_event_bus, reset_event_bus
from geofront_api.jobs import reset_job_manager
from geofront_api.main import create_app
from geofront_api.state import reset_state

# ──────────────────────────────────────────────────────────────────────────────
# Manual ASGI harness for the SSE route.
#
# Both starlette TestClient and httpx.ASGITransport await the ASGI app to
# completion before returning a response — an infinite event stream deadlocks
# them. Driving `app(scope, receive, send)` directly gives control over the
# stream lifecycle; regular routes still go through httpx.ASGITransport.
# ──────────────────────────────────────────────────────────────────────────────


def _events_scope() -> dict[str, Any]:
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/v1/events",
        "raw_path": b"/api/v1/events",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"testserver"),
            (b"accept", b"text/event-stream"),
        ],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }


class SSESession:
    """Runs one GET /api/v1/events against the app; yields parsed SSE events."""

    def __init__(self) -> None:
        self.status_code: int | None = None
        self.headers: list[tuple[str, str]] = []
        self._chunks: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._buffer = b""
        self._disconnect = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._started = asyncio.Event()

    async def start(self, app: Any) -> None:
        async def receive() -> dict[str, Any]:
            await self._disconnect.wait()
            return {"type": "http.disconnect"}

        async def send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                self.status_code = message["status"]
                self.headers = [(k.decode(), v.decode()) for k, v in message["headers"]]
                self._started.set()
            elif message["type"] == "http.response.body":
                body: bytes = message.get("body", b"")
                if body:
                    await self._chunks.put(body)
                if not message.get("more_body", False):
                    await self._chunks.put(None)

        self._task = asyncio.create_task(app(_events_scope(), receive, send))
        await asyncio.wait_for(self._started.wait(), timeout=5.0)

    async def next_event(self, timeout: float = 5.0) -> tuple[str, Any]:
        """Return the next complete `(event, data)` pair."""
        while True:
            while b"\n\n" in self._buffer:
                block, self._buffer = self._buffer.split(b"\n\n", 1)
                event_name: str | None = None
                data_raw: str | None = None
                for line in block.decode("utf-8").splitlines():
                    if line.startswith("event: "):
                        event_name = line[len("event: ") :]
                    elif line.startswith("data: ") and data_raw is None:
                        data_raw = line[len("data: ") :]
                if event_name is not None:
                    data = json.loads(data_raw) if data_raw else None
                    return event_name, data
                # else: comment block (e.g. ": ping") — keep reading
            chunk = await asyncio.wait_for(self._chunks.get(), timeout=timeout)
            assert chunk is not None, "stream ended before the expected event"
            self._buffer += chunk

    async def close(self) -> None:
        """Signal disconnect, then wait for the app call to finish."""
        self._disconnect.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(self._task), timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()


class TestEventBus:
    def test_publish_from_thread_reaches_subscriber(self) -> None:
        async def scenario() -> None:
            bus = EventBus()
            bus.bind(asyncio.get_running_loop())
            queue = await bus.subscribe()

            def publish_from_thread() -> None:
                bus.publish("job_progress", {"id": "j1", "status": "completed"})

            await asyncio.to_thread(publish_from_thread)
            record = await asyncio.wait_for(queue.get(), timeout=2.0)
            assert record["event"] == "job_progress"
            assert record["data"]["id"] == "j1"

        asyncio.run(scenario())

    def test_publish_without_loop_is_noop(self) -> None:
        bus = EventBus()  # never bound
        bus.publish("anything", {})  # must not raise

    def test_flood_does_not_block(self) -> None:
        async def scenario() -> None:
            bus = EventBus()
            bus.bind(asyncio.get_running_loop())
            await bus.subscribe()

            def flood() -> None:
                for i in range(events_mod._SUBSCRIBER_QUEUE_SIZE * 2):
                    bus.publish("job_progress", {"i": i})

            # Publishing far beyond queue capacity must not block the thread.
            await asyncio.wait_for(asyncio.to_thread(flood), timeout=5.0)

        asyncio.run(scenario())


class TestSSEEndpoint:
    def _reset(self) -> None:
        reset_state()
        reset_job_manager()
        reset_event_bus()

    async def _make_app_and_client(self) -> tuple[Any, httpx.AsyncClient]:
        app = create_app()
        get_event_bus().bind(asyncio.get_running_loop())
        ac = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        )
        return app, ac

    def _run(self, scenario) -> None:
        async def wrapped() -> None:
            self._reset()
            try:
                app, ac = await self._make_app_and_client()
                async with ac:
                    await asyncio.wait_for(scenario(app, ac), timeout=30.0)
            finally:
                self._reset()

        asyncio.run(wrapped())

    def test_stream_hello_and_headers(self) -> None:
        async def scenario(app: Any, ac: httpx.AsyncClient) -> None:
            session = SSESession()
            await session.start(app)
            assert session.status_code == 200
            assert any(k.lower() == "content-type" and v.startswith("text/event-stream")
                       for k, v in session.headers)
            assert any(k.lower() == "cache-control" and v == "no-cache"
                       for k, v in session.headers)
            event, _data = await session.next_event()
            assert event == "hello"
            await session.close()

        self._run(scenario)

    def test_collection_created_broadcast(self, tmp_path: Path) -> None:
        async def scenario(app: Any, ac: httpx.AsyncClient) -> None:
            r = await ac.post(
                "/api/v1/workspace/create", json={"path": str(tmp_path / "ws"), "name": "sse"}
            )
            assert r.status_code == 201

            session = SSESession()
            await session.start(app)
            event, _ = await session.next_event()
            assert event == "hello"

            r = await ac.post("/api/v1/collections", json={"name": "sse-col"})
            assert r.status_code == 201

            deadline_events = [await session.next_event()]
            while deadline_events[-1][0] != "collection_created":
                deadline_events.append(await session.next_event())
            name = deadline_events[-1][1]["name"]
            assert name == "sse-col"
            await session.close()

        self._run(scenario)

    def test_job_progress_and_asset_created_broadcast(self, tmp_path: Path) -> None:
        async def scenario(app: Any, ac: httpx.AsyncClient) -> None:
            r = await ac.post(
                "/api/v1/workspace/create", json={"path": str(tmp_path / "ws"), "name": "sse"}
            )
            assert r.status_code == 201
            cid = (await ac.post("/api/v1/collections", json={"name": "c"})).json()["id"]

            session = SSESession()
            await session.start(app)
            event, _ = await session.next_event()
            assert event == "hello"

            ingest = await ac.post(
                "/api/v1/ingest/bytes",
                json={
                    "filename": "sse.txt",
                    "data_base64": base64.b64encode(b"sse broadcast probe\n" * 4).decode(),
                    "collection_id": cid,
                    "index_after": False,
                },
            )
            assert ingest.status_code == 202
            job_id = ingest.json()["job_id"]

            statuses: list[str] = []
            asset_event: dict | None = None
            # asset_created fires from inside the job thread before the
            # completed progress event — keep reading until both arrive.
            for _ in range(60):
                if asset_event is not None and "completed" in statuses:
                    break
                event, data = await session.next_event()
                if event == "job_progress" and data.get("id") == job_id:
                    statuses.append(data["status"])
                if event == "asset_created" and data.get("collection_id") == cid:
                    asset_event = data
            assert asset_event is not None, f"asset_created never arrived; saw {statuses}"
            assert "completed" in statuses

            job = await ac.get(f"/api/v1/jobs/{job_id}")
            assert job.json()["status"] == "completed"
            assert asset_event["asset_id"] == job.json()["result"]["asset_id"]
            await session.close()

        self._run(scenario)

    def test_workspace_changed_broadcast(self, tmp_path: Path) -> None:
        async def scenario(app: Any, ac: httpx.AsyncClient) -> None:
            session = SSESession()
            await session.start(app)
            event, _ = await session.next_event()
            assert event == "hello"

            r = await ac.post(
                "/api/v1/workspace/create",
                json={"path": str(tmp_path / "ws2"), "name": "sse"},
            )
            assert r.status_code == 201

            for _ in range(20):
                event, data = await session.next_event()
                if event == "workspace_changed":
                    assert data["status"] == "open"
                    break
            else:
                raise AssertionError("workspace_changed event never arrived")
            await session.close()

        self._run(scenario)

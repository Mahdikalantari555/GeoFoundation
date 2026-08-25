from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from .conftest import make_collection, wait_job


class TestCollections:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.get("/api/v1/collections")
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "workspace_not_open"

    def test_crud(self, client: TestClient, open_ws: dict) -> None:
        resp = client.post(
            "/api/v1/collections", json={"name": "papers", "description": "RS papers"}
        )
        assert resp.status_code == 201
        col = resp.json()
        assert col["name"] == "papers"
        assert col["description"] == "RS papers"
        assert col["archived"] in (True, False, None)
        cid = col["id"]

        resp = client.get("/api/v1/collections")
        assert [c["id"] for c in resp.json()] == [cid]

        resp = client.get(f"/api/v1/collections/{cid}")
        assert resp.json()["name"] == "papers"

        resp = client.delete(f"/api/v1/collections/{cid}")
        assert resp.json() == {"archived": True, "id": cid}

        # archived collections are not listed
        assert client.get("/api/v1/collections").json() == []

        # get on archived → 404 (archived means gone for the facade)
        resp = client.get(f"/api/v1/collections/{cid}")
        assert resp.status_code == 404

    def test_get_missing_404(self, client: TestClient, open_ws: dict) -> None:
        resp = client.get("/api/v1/collections/nope")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "collection_not_found"

    def test_validation(self, client: TestClient, open_ws: dict) -> None:
        resp = client.post("/api/v1/collections", json={"name": ""})
        assert resp.status_code == 422


class TestIngest:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ingest/bytes",
            json={
                "filename": "a.txt",
                "data_base64": base64.b64encode(b"hello").decode(),
                "collection_id": "x",
            },
        )
        assert resp.status_code == 409

    def test_unsupported_extension(self, client: TestClient, open_ws: dict) -> None:
        cid = make_collection(client)
        resp = client.post(
            "/api/v1/ingest/bytes",
            json={
                "filename": "evil.exe",
                "data_base64": base64.b64encode(b"MZ").decode(),
                "collection_id": cid,
            },
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "unsupported_format"

    def test_bytes_lifecycle_and_dedup(self, client: TestClient, open_ws: dict) -> None:
        cid = make_collection(client)
        payload = base64.b64encode(
            b"# Sugarcane stress\nNDVI drops under water stress.\n" * 20
        ).decode()

        resp = client.post(
            "/api/v1/ingest/bytes",
            json={
                "filename": "notes.md",
                "data_base64": payload,
                "collection_id": cid,
                "index_after": False,
            },
        )
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        job = wait_job(client, job_id)
        assert job["status"] == "completed", job
        result = job["result"]
        assert result.get("skipped") is not True
        assert result["segment_count"] >= 1
        asset_id = result["asset_id"]

        # assets listed under collection
        resp = client.get("/api/v1/assets", params={"collection_id": cid})
        assert [a["id"] for a in resp.json()] == [asset_id]

        # inspect shape
        detail = client.get(f"/api/v1/assets/{asset_id}").json()
        assert detail["asset"]["id"] == asset_id
        assert "revision" in detail and "segments" in detail

        # dedup: same bytes again → skipped
        resp = client.post(
            "/api/v1/ingest/bytes",
            json={
                "filename": "copy.md",
                "data_base64": payload,
                "collection_id": cid,
                "index_after": False,
            },
        )
        job2 = wait_job(client, resp.json()["job_id"])
        assert job2["status"] == "completed"
        assert job2["result"]["skipped"] is True

    def test_multipart_upload(self, client: TestClient, open_ws: dict) -> None:
        cid = make_collection(client)
        resp = client.post(
            "/api/v1/ingest",
            data={"collection_id": cid, "index_after": "false"},
            files={"file": ("readme.txt", b"thermal stress indicators", "text/plain")},
        )
        assert resp.status_code == 202
        job = wait_job(client, resp.json()["job_id"])
        assert job["status"] == "completed"
        assert job["result"].get("skipped") is not True

    def test_unknown_collection(self, client: TestClient, open_ws: dict) -> None:
        resp = client.post(
            "/api/v1/ingest/bytes",
            json={
                "filename": "a.txt",
                "data_base64": base64.b64encode(b"data").decode(),
                "collection_id": "missing",
                "index_after": False,
            },
        )
        job = wait_job(client, resp.json()["job_id"])
        assert job["status"] == "failed"
        assert "Collection" in job["error"]


class TestJobs:
    def test_missing_job_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/jobs/zzz")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "job_not_found"

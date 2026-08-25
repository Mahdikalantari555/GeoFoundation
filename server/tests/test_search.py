from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from .conftest import make_collection, wait_job


def ingest_text(
    client: TestClient, collection_id: str, text: bytes, filename: str = "notes.md"
) -> dict:
    resp = client.post(
        "/api/v1/ingest/bytes",
        json={
            "filename": filename,
            "data_base64": base64.b64encode(text).decode(),
            "collection_id": collection_id,
            "index_after": False,
        },
    )
    assert resp.status_code == 202
    job = wait_job(client, resp.json()["job_id"])
    assert job["status"] == "completed", job
    return job  # type: ignore[no-any-return]


class TestSearch:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.post("/api/v1/search", json={"query": "ndvi"})
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "workspace_not_open"

    def test_empty_query_422(self, client: TestClient, open_ws: dict) -> None:
        resp = client.post("/api/v1/search", json={"query": ""})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation"

    def test_invalid_mode_422(self, client: TestClient, open_ws: dict) -> None:
        resp = client.post("/api/v1/search", json={"query": "ndvi", "mode": "bogus"})
        assert resp.status_code == 422

    def test_search_lifecycle(self, client: TestClient, open_ws: dict) -> None:
        cid = make_collection(client)
        ingest_text(
            client,
            cid,
            b"# Sugarcane monitoring\n"
            b"NDVI drops sharply under severe water stress in irrigated fields.\n" * 10,
        )

        resp = client.post(
            "/api/v1/search", json={"query": "NDVI water stress", "mode": "hybrid", "top_n": 5}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["query"] == "NDVI water stress"
        assert body["query_plan"]["mode"] == "hybrid"
        assert body["total_hits"] >= 1
        assert body["retrieval_run_id"]
        assert isinstance(body["latency_ms"], int)
        hit = body["hits"][0]
        assert hit["id"]
        assert isinstance(hit["score"], float)
        assert "text" in hit and "locator" in hit and "metadata" in hit

        # sparse-only: still works offline via FTS5
        resp = client.post(
            "/api/v1/search", json={"query": "sugarcane", "mode": "sparse", "top_n": 3}
        )
        assert resp.status_code == 200
        assert resp.json()["total_hits"] >= 1

        # dense-only: numpy char n-gram fallback keeps it functional offline
        resp = client.post(
            "/api/v1/search", json={"query": "sugarcane", "mode": "dense", "top_n": 3}
        )
        assert resp.status_code == 200
        assert resp.json()["query_plan"]["mode"] == "dense"

    def test_collection_filter(self, client: TestClient, open_ws: dict) -> None:
        cid = make_collection(client)
        make_collection(client, "empty")
        ingest_text(
            client, cid, b"Landsat thermal band brightness temperature\n" * 5, "thermal.md"
        )
        resp = client.post(
            "/api/v1/search",
            json={"query": "thermal brightness", "collections": [cid]},
        )
        assert resp.status_code == 200
        assert resp.json()["total_hits"] >= 1

    def test_spatial_filter(self, client: TestClient, open_ws: dict) -> None:
        make_collection(client)
        # valid bbox — empty result set is fine (post-fusion filter)
        resp = client.post(
            "/api/v1/search",
            json={"query": "anything", "spatial": {"op": "intersects", "bbox": [50.0, 29.0, 51.0, 30.0]}},
        )
        assert resp.status_code == 200
        assert "hits" in resp.json()

    def test_spatial_filter_invalid(self, client: TestClient, open_ws: dict) -> None:
        for bad in (
            {"op": "intersects"},  # neither bbox nor geometry_id
            {"op": "intersects", "bbox": [10.0, 20.0, 5.0, 30.0]},  # min > max
            {"op": "intersects", "bbox": [0.0, 0.0, 200.0, 10.0]},  # out of WGS84 range
            {"op": "distance_lte", "bbox": [0.0, 0.0, 1.0, 1.0]},  # distance_lte w/o distance_m
        ):
            resp = client.post("/api/v1/search", json={"query": "q", "spatial": bad})
            assert resp.status_code == 422, bad
            assert resp.json()["error"]["code"] == "invalid_spatial_filter", bad

        # unknown fields inside the filter → request validation envelope
        resp = client.post(
            "/api/v1/search",
            json={"query": "q", "spatial": {"op": "intersects", "bbox": [0.0, 0.0, 1.0, 1.0], "bogus": 1}},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation"

    def test_temporal_filter(self, client: TestClient, open_ws: dict) -> None:
        make_collection(client)
        resp = client.post(
            "/api/v1/search",
            json={
                "query": "crop",
                "temporal": {"field": "observed_at", "from": "2000-01-01", "to": "2099-01-01"},
            },
        )
        assert resp.status_code == 200

    def test_temporal_filter_invalid(self, client: TestClient, open_ws: dict) -> None:
        for bad in (
            {},  # neither from nor to
            {"from": "2099-01-01", "to": "2000-01-01"},  # from > to
            {"from": "2000-01-01", "field": "bogus_field"},  # unknown field name
        ):
            resp = client.post("/api/v1/search", json={"query": "q", "temporal": bad})
            assert resp.status_code == 422, bad
            assert resp.json()["error"]["code"] in (
                "invalid_temporal_filter",
                "validation",
            ), bad

    def test_unknown_fields_rejected(self, client: TestClient, open_ws: dict) -> None:
        resp = client.post("/api/v1/search", json={"query": "q", "bogus": True})
        assert resp.status_code == 422


class TestAsk:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.post("/api/v1/ask", json={"question": "what?"})
        assert resp.status_code == 409

    def test_empty_question_422(self, client: TestClient, open_ws: dict) -> None:
        resp = client.post("/api/v1/ask", json={"question": ""})
        assert resp.status_code == 422

    def test_invalid_mode_422(self, client: TestClient, open_ws: dict) -> None:
        resp = client.post("/api/v1/ask", json={"question": "q", "mode": "bogus"})
        assert resp.status_code == 422

    def test_ask_abstains_without_llm(self, client: TestClient, open_ws: dict) -> None:
        cid = make_collection(client)
        ingest_text(
            client,
            cid,
            b"# Irrigation\nSugarcane fields under deficit irrigation show NDVI decline.\n" * 8,
        )
        # context exists but no LLM backend (offline workspace, no GGUF, no API key)
        resp = client.post(
            "/api/v1/ask", json={"question": "What happens to NDVI under deficit irrigation?"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["abstained"] is True
        assert body["abstention_reason"]
        assert body["model"] == "none"
        assert "citations" in body and "sources" in body

    def test_ask_abstains_no_context(self, client: TestClient, open_ws: dict) -> None:
        make_collection(client)
        resp = client.post("/api/v1/ask", json={"question": "quantum chromodynamics"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["abstained"] is True
        assert body["abstention_reason"]

    def test_ask_with_filters(self, client: TestClient, open_ws: dict) -> None:
        cid = make_collection(client)
        ingest_text(client, cid, b"Soil salinity mapping with Sentinel-2\n" * 5, "salinity.md")
        resp = client.post(
            "/api/v1/ask",
            json={
                "question": "How is soil salinity mapped?",
                "mode": "research",
                "collections": [cid],
                "spatial": {"bbox": [45.0, 25.0, 46.0, 26.0]},
                "temporal": {"from": "2000-01-01", "to": "2099-01-01"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["abstained"] is True  # still abstains offline — filters accepted

    def test_ask_invalid_filter_422(self, client: TestClient, open_ws: dict) -> None:
        resp = client.post(
            "/api/v1/ask",
            json={"question": "q", "spatial": {"op": "intersects"}},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "invalid_spatial_filter"


class TestFeedback:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/feedback",
            json={"target_type": "segment", "target_id": "seg_1", "label": "source_relevance"},
        )
        assert resp.status_code == 409

    def test_record_feedback(self, client: TestClient, open_ws: dict) -> None:
        cid = make_collection(client)
        job = ingest_text(client, cid, b"feedback target\n" * 5, "fb.md")
        asset_id = job["result"]["asset_id"]
        # find a segment id via inspect
        detail = client.get(f"/api/v1/assets/{asset_id}").json()
        segment_id = detail["segments"][0]["id"]

        resp = client.post(
            "/api/v1/feedback",
            json={
                "target_type": "segment",
                "target_id": segment_id,
                "label": "source_relevance",
                "payload": {"rating": 1, "query": "feedback target"},
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"].startswith("fb")
        assert body["target_id"] == segment_id
        assert body["label"] == "source_relevance"

        # events are immutable but repeat recording is allowed (new id)
        resp2 = client.post(
            "/api/v1/feedback",
            json={"target_type": "segment", "target_id": segment_id, "label": "source_relevance"},
        )
        assert resp2.status_code == 201
        assert resp2.json()["id"] != body["id"]

    def test_invalid_target_type_422(self, client: TestClient, open_ws: dict) -> None:
        resp = client.post(
            "/api/v1/feedback",
            json={"target_type": "galaxy", "target_id": "x", "label": "l"},
        )
        assert resp.status_code == 422

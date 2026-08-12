"""Workspace lifecycle and the public GeoMemory class."""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from geomemory.core.config import load_settings, save_settings, settings_from_dict
from geomemory.core.events import (
    ASSET_CREATED,
    COLLECTION_CREATED,
    DomainEvent,
    EventBus,
)
from geomemory.core.exceptions import (
    AssetNotFoundError,
    CollectionNotFoundError,
    WorkspaceNotFoundError,
)
from geomemory.core.hashing import sha256_bytes
from geomemory.core.models import (
    Asset,
    AssetDetail,
    AssetRevision,
    BenchmarkResult,
    Collection,
    DatasetExample,
    FeedbackEvent,
    Job,
    QAResult,
    QueryPlan,
    RetrievalRun,
    SearchFilters,
    SearchHit,
    SearchRequest,
    SearchResult,
    Segment,
    SpatialFilter,
    TemporalFilter,
    VectorLayer,
    WorkspaceConfig,
    WorkspaceSettings,
)
from geomemory.core.models import (
    Workspace as WorkspaceModel,
)
from geomemory.retrieval.search_service import SearchService
from geomemory.retrieval.spatial_filter import apply_spatial_filter
from geomemory.retrieval.temporal_filter import apply_temporal_filter
from geomemory.storage import connect, initialize, migrate, schema_sql
from geomemory.storage.object_store import ObjectStore

WORKSPACE_MARKER = ".geomemory"
DB_FILENAME = "geomemory.db"
SETTINGS_FILENAME = "workspace.yaml"

# Default storage directory names (can be overridden via settings).
DEFAULT_OBJECTS_DIR = "objects"
DEFAULT_INDEX_DIR = "indexes"
DEFAULT_LOGS_DIR = "logs"


class Workspace:
    """A GeoMemory workspace.

    To create or open a workspace use :class:`GeoMemory` (the public entry
    point). This class wires the SQLite database, object store, and indexes
    together.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        create: bool = False,
        config: WorkspaceConfig | None = None,
    ) -> None:
        self.path = Path(path)
        self._closed = False
        self.events = EventBus()

        if create:
            self._create(config or WorkspaceConfig())
        else:
            self._open_existing()

        self.db_path = self.path / DB_FILENAME
        self.objects_dir = self.path / self.settings.objects_dir
        self.index_dir = self.path / self.settings.index_dir
        self.logs_dir = self.path / self.settings.logs_dir

        # Connection uses check_same_thread=False so it survives Streamlit
        # rerun threads (each rerun runs in a different OS thread). Streamlit
        # serializes script execution, so access is effectively single-threaded
        # at the application level; the connection is never shared concurrently.
        self.conn = connect(self.db_path)
        initialize(self.conn)
        migrate(self.conn, schema_sql())

        self.objects = ObjectStore(self.path / DEFAULT_OBJECTS_DIR)

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def _create(self, config: WorkspaceConfig) -> None:
        if self.path.exists() and any(self.path.iterdir()):
            from geomemory.core.exceptions import WorkspaceExistsError

            raise WorkspaceExistsError(
                f"Cannot create workspace at {self.path}: directory is not empty"
            )
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / WORKSPACE_MARKER).touch()
        settings = settings_from_dict(config.model_dump())
        save_settings(self.path / SETTINGS_FILENAME, settings)
        self._settings = settings

    def _open_existing(self) -> None:
        if not (self.path / WORKSPACE_MARKER).is_file():
            raise WorkspaceNotFoundError(
                f"No GeoMemory workspace found at {self.path} "
                f"(missing {WORKSPACE_MARKER} marker)"
            )
        self._settings = load_settings(self.path / SETTINGS_FILENAME)

    @property
    def settings(self) -> WorkspaceSettings:
        """Persisted workspace settings."""
        return self._settings

    def update_settings(self, **changes: Any) -> WorkspaceSettings:
        """Update and persist workspace settings (validated).

        Accepts any ``WorkspaceSettings`` field, e.g. ``model_path``,
        ``embedding_path``, ``batch_size``. Returns the updated settings.
        """
        merged = self._settings.model_dump()
        for key, value in changes.items():
            if key not in WorkspaceSettings.model_fields:
                raise ValueError(f"Unknown setting: {key}")
            merged[key] = value
        updated = WorkspaceSettings(**merged)
        save_settings(self.path / SETTINGS_FILENAME, updated)
        self._settings = updated
        return updated

    def close(self) -> None:
        """Close the database connection."""
        if not self._closed:
            self.conn.close()
            self._closed = True

    def __enter__(self) -> Workspace:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ── Collections ──────────────────────────────────────────────────────────

    def create_collection(self, name: str, description: str = "") -> Collection:
        """Create a collection, emitting a ``collection_created`` event."""
        collection = Collection(
            workspace_id=self._workspace_id(), name=name, description=description
        )
        self.conn.execute(
            "INSERT INTO collection (id, workspace_id, name, description, created_at, archived) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            (collection.id, collection.workspace_id, collection.name, collection.description, collection.created_at),
        )
        self.conn.commit()
        self.events.emit(
            DomainEvent(
                event_type=COLLECTION_CREATED,
                entity_id=collection.id,
                payload={"name": name, "workspace_id": self._workspace_id()},
            )
        )
        return collection

    def list_collections(self) -> list[Collection]:
        """Return all non-archived collections."""
        rows = self.conn.execute(
            "SELECT * FROM collection WHERE archived = 0 ORDER BY created_at"
        ).fetchall()
        return [Collection(**dict(r)) for r in rows]

    def get_collection(self, collection_id: str) -> Collection | None:
        """Return a collection by id, or None."""
        row = self.conn.execute(
            "SELECT * FROM collection WHERE id = ? AND archived = 0", (collection_id,)
        ).fetchone()
        return Collection(**dict(row)) if row is not None else None

    def archive_collection(self, collection_id: str) -> bool:
        """Soft-delete a collection. Returns True if archived."""
        cur = self.conn.execute(
            "UPDATE collection SET archived = 1 WHERE id = ?", (collection_id,)
        )
        self.conn.commit()
        return cur.rowcount > 0

    # ── Ingestion (synchronous core) ────────────────────────────────────────

    def ingest(
        self,
        source: str | Path | bytes,
        collection_id: str,
        *,
        parser: str | None = None,
        index_after: bool = True,
    ) -> Job:
        """Ingest a file or raw bytes into a collection.

        This executes the full pipeline synchronously and returns a completed
        ``Job``. Background execution is provided by the ingestion service.
        """
        collection = self.get_collection(collection_id)
        if collection is None:
            raise CollectionNotFoundError(f"Collection not found: {collection_id}")

        if isinstance(source, (str, Path)):
            src_path = Path(source)
            if not src_path.is_file():
                raise FileNotFoundError(f"Source file not found: {src_path}")
            raw = src_path.read_bytes()
            source_ref_path = str(src_path)
        elif isinstance(source, bytes):
            raw = source
            source_ref_path = "<bytes>"
        else:
            raise TypeError("source must be str, Path, or bytes")

        content_hash = sha256_bytes(raw)
        mime_type = _detect_mime(Path(source_ref_path))

        # Dedup check: reuse existing revision with same hash.
        existing = self.conn.execute(
            "SELECT * FROM asset_revision WHERE hash = ? LIMIT 1", (content_hash,)
        ).fetchone()
        if existing is not None:
            asset = self._asset_by_id(existing["asset_id"])
            segment_ids = self._segments_for_revision(existing["id"])
            if segment_ids is None:
                segment_ids = []
            return _job_completed(
                "ingestion",
                {
                    "asset_id": asset.id,
                    "revision_id": existing["id"],
                    "skipped": True,
                    "reason": "duplicate hash",
                },
            )

        # Parse + chunk the document.
        kind = _kind_for_mime(mime_type)
        spatial_payload: dict[str, Any] | None = None
        if kind in ("raster", "vector"):
            chunks, spatial_payload = self._parse_spatial_source(source_ref_path, kind)
        else:
            chunks = _chunk_document(raw, mime_type, source_ref_path, parser=parser)

        # Store raw bytes in object store.
        stored_hash = self.objects.put_bytes(raw)
        assert stored_hash == content_hash

        # Create asset + revision.
        asset = Asset(collection_id=collection_id, kind=kind, title=Path(source_ref_path).name)
        asset_id = asset.id
        revision = AssetRevision(
            asset_id=asset_id,
            hash=content_hash,
            mime_type=mime_type,
            size_bytes=len(raw),
            parser_version="0.1.0",
        )
        self.conn.execute(
            "INSERT INTO asset (id, collection_id, kind, title, current_revision_id, deleted_at, created_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, NULL, ?, ?)",
            (
                asset.id,
                asset.collection_id,
                asset.kind,
                asset.title,
                None,
                asset.created_at,
                json.dumps(asset.metadata),
            ),
        )
        self.conn.execute(
            "INSERT INTO asset_revision (id, asset_id, hash, mime_type, size_bytes, parser_version, ingested_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                revision.id,
                revision.asset_id,
                revision.hash,
                revision.mime_type,
                revision.size_bytes,
                revision.parser_version,
                revision.ingested_at,
                json.dumps(revision.metadata),
            ),
        )
        # Store segments (locators preserved; spatial metadata for rs assets).
        segment_ids: list[str] = []
        for chunk in chunks:
            meta = chunk.get("metadata") or {}
            segment = Segment(
                revision_id=revision.id,
                segment_type=chunk["segment_type"],
                text=chunk["text"],
                locator=chunk["locator"],
                metadata=meta,
            )
            self.conn.execute(
                "INSERT INTO segment (id, revision_id, segment_type, text, locator, parent_section_id, neighbor_ids, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?, NULL, '[]', ?, ?)",
                (
                    segment.id,
                    segment.revision_id,
                    segment.segment_type,
                    segment.text,
                    json.dumps(segment.locator),
                    json.dumps(meta),
                    segment.created_at,
                ),
            )
            segment_ids.append(segment.id)

        # Persist raster scenes / vector layers and their spatial index entries.
        if spatial_payload is not None:
            if kind == "raster":
                from geomemory.rs.persist import persist_scene

                persist_scene(
                    self.conn,
                    revision.id,
                    spatial_payload["scene"],
                    tiles=spatial_payload.get("tiles"),
                )
            elif kind == "vector":
                from geomemory.rs.persist import persist_vector_layer

                persist_vector_layer(self.conn, revision.id, spatial_payload["layer"])

        self.conn.execute(
            "UPDATE asset SET current_revision_id = ? WHERE id = ?", (revision.id, asset.id)
        )
        self.conn.commit()

        self.events.emit(
            DomainEvent(
                event_type=ASSET_CREATED,
                entity_id=asset.id,
                payload={
                    "revision_id": revision.id,
                    "hash": content_hash,
                    "mime_type": mime_type,
                    "segment_count": len(segment_ids),
                },
            )
        )

        return _job_completed(
            "ingestion",
            {"asset_id": asset.id, "revision_id": revision.id, "segment_count": len(segment_ids)},
        )

    def _parse_spatial_source(
        self, source_path: str, kind: str
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Parse a raster/vector source via the rs loaders into chunks + payload."""
        from geomemory.core.exceptions import UnsupportedFormatError
        from geomemory.core.models import SourceRef
        from geomemory.ingest.loaders.geojson import GeoJsonLoader
        from geomemory.ingest.loaders.geotiff import GeoTiffLoader
        from geomemory.rs.persist import spatial_metadata

        loader = (
            GeoTiffLoader(artifact_dir=self.path / "artifacts")
            if kind == "raster"
            else GeoJsonLoader()
        )
        parsed = list(loader.load(SourceRef(path=source_path)))
        if not parsed:
            raise UnsupportedFormatError(f"No spatial content parsed from {source_path}")
        obj = parsed[0]
        payload = obj.metadata.get("raster") or obj.metadata.get("vector") or {}
        scene = payload.get("scene")
        layer = payload.get("layer")
        spatial: dict[str, Any] = {}
        if scene:
            spatial = spatial_metadata(
                bbox=scene.get("bbox"),
                acquired_at=scene.get("acquired_at"),
                sensor=scene.get("sensor"),
            )
        elif layer:
            spatial = spatial_metadata(bbox=layer.get("bbox"))
        chunks = [
            {
                "text": obj.text,
                "segment_type": "paragraph",
                "locator": {"file": source_path},
                "metadata": {"spatial": spatial} if spatial else {},
            }
        ]
        return chunks, payload

    # ── Search (sparse FTS5 + dense numpy fallback) ─────────────────────────

    def search(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        top_k: int = 20,
        top_n: int = 5,
        collections: list[str] | None = None,
        spatial: SpatialFilter | None = None,
        temporal: TemporalFilter | None = None,
        sensor: list[str] | None = None,
    ) -> SearchResult:
        """Execute a hybrid search.

        Sparse retrieval uses SQLite FTS5. Dense retrieval uses a
        character n-gram based NumpyBackend when no embedding model is loaded,
        so ``search()`` always works offline. Fusion is Reciprocal Rank Fusion.
        """
        start = time.perf_counter()
        query = (query or "").strip()
        filters = SearchFilters(
            collections=collections, sensors=sensor, spatial=spatial, temporal=temporal
        )
        plan = QueryPlan(intent="search", mode=mode, top_k=top_k, top_n=top_n, filters=filters)

        sparse_hits = self._fts_search(query, top_k=top_k, collections=collections)
        dense_hits: list[SearchHit] = []
        if mode in ("dense", "hybrid"):
            dense_hits = self._dense_search(query, top_k=top_k, collections=collections)

        fused = _rrf_fuse([sparse_hits, dense_hits], top_n=top_n)
        fused = apply_spatial_filter(fused, spatial)
        fused = apply_temporal_filter(fused, temporal)
        if sensor:
            fused = [
                hit for hit in fused if _hit_sensor(hit) is not None and _hit_sensor(hit) in sensor
            ]

        latency_ms = int((time.perf_counter() - start) * 1000)
        run = RetrievalRun(
            query=query,
            query_plan=plan.model_dump(),
            filters=filters.model_dump(),
            config={"mode": mode, "top_k": top_k, "top_n": top_n, "fusion": "rrf"},
            latency_ms=latency_ms,
        )
        self._save_retrieval_run(run, [h.model_dump() for h in fused])

        result = SearchResult(
            query=query,
            query_plan=plan,
            hits=fused,
            total_hits=len(fused),
            latency_ms=latency_ms,
            retrieval_run_id=run.id,
        )
        return result

    def _fts_search(self, query: str, *, top_k: int, collections: list[str] | None) -> list[SearchHit]:
        """Run a FTS5 full-text query over segment text."""
        if not query:
            return []
        rows = self._fts_match(query, top_k, collections)
        hits: list[SearchHit] = []
        for r in rows:
            try:
                meta = json.loads(r["metadata"]) if r["metadata"] else {}
            except (json.JSONDecodeError, TypeError):
                meta = {}
            hits.append(
                SearchHit(
                    id=r["id"],
                    sparse_score=float(r["score"]),
                    text=r["text"],
                    locator=json.loads(r["locator"]),
                    metadata={
                        "segment_type": r["segment_type"],
                        "revision_id": r["revision_id"],
                        **meta,
                    },
                )
            )
        return hits

    def _fts_match(self, query: str, top_k: int, collections: list[str] | None) -> list[Any]:
        """Return FTS5 match rows (safely wrapping the MATCH syntax)."""
        terms = _FTS_TERM_RE.findall(query)
        if not terms:
            return []
        fts_query = " OR ".join(terms)
        sql = (
            "SELECT s.id, s.text, s.locator, s.revision_id, s.segment_type, s.metadata, "
            "bm25(segments_fts) AS score "
            "FROM segments_fts JOIN segment s ON s.rowid = segments_fts.rowid "
            "WHERE segments_fts MATCH ? "
        )
        params: list[Any] = [fts_query]
        if collections:
            placeholders = ",".join("?" for _ in collections)
            sql += " AND s.revision_id IN (SELECT id FROM asset_revision WHERE asset_id IN "
            sql += f"(SELECT id FROM asset WHERE collection_id IN ({placeholders})))"
            params.extend(collections)
        sql += " ORDER BY score LIMIT ?"
        params.append(top_k)
        return self.conn.execute(sql, params).fetchall()

    def _dense_search(
        self, query: str, *, top_k: int, collections: list[str] | None = None
    ) -> list[SearchHit]:
        """Dense search over the persisted index, falling back to n-gram TF.

        When a persisted index exists for the active space it is used;
        otherwise a NumpyBackend is built on demand from SQLite so search
        always works offline. Collection-filtered queries use the on-demand
        backend because the persisted index is global.
        """
        if collections:
            return self._numpy_dense_search(query, top_k=top_k, collections=collections)
        space_id = getattr(self, "_index_space", None) or "text.hash.v1"
        try:
            from geomemory.services.index_service import IndexService

            hits = IndexService(
                self.conn, self.index_dir, batch_size=self.settings.batch_size
            ).search(
                query,
                space_id=space_id,
                top_k=top_k,
                model_path=self.settings.embedding_path,
            )
            if hits:
                return hits
        except Exception:
            # Fall through to the on-demand n-gram backend.
            pass
        return self._numpy_dense_search(query, top_k=top_k, collections=collections)

    def _numpy_dense_search(
        self, query: str, *, top_k: int, collections: list[str] | None = None
    ) -> list[SearchHit]:
        """Ngram-based vector search over stored segments (no model required)."""
        try:
            from geomemory.index.numpy_backend import NumpyBackend
        except ImportError:
            return []
        backend = NumpyBackend.from_database(self.conn, collections=collections)
        if backend.count() == 0:
            return []
        request = SearchRequest(query=query, mode="dense", top_k=top_k, top_n=top_k)
        return backend.search(request)

    # ── QA ──────────────────────────────────────────────────────────────────

    def ask(
        self,
        question: str,
        *,
        mode: str = "grounded_qa",
        collections: list[str] | None = None,
        filters: SearchFilters | None = None,
    ) -> QAResult:
        """Answer a question using retrieved context.

        Without a loaded LLM, the system abstains with a clear reason.
        Grounded answers require a local GGUF model configured in settings.
        """
        if not (question or "").strip():
            return QAResult(
                text="",
                abstained=True,
                abstention_reason="Empty question",
                model="none",
            )
        result = self.search(question, collections=collections)
        if not result.hits:
            return QAResult(
                text="not found in selected sources",
                abstained=True,
                abstention_reason="No relevant context found",
                sources=result.hits,
                retrieval_run_id=result.retrieval_run_id,
                latency_ms=result.latency_ms,
                model="none",
            )
        model_path = self.settings.model_path
        if not model_path:
            return QAResult(
                text="not found in selected sources",
                abstained=True,
                abstention_reason="No LLM backend configured (set model_path in workspace.yaml)",
                sources=result.hits,
                retrieval_run_id=result.retrieval_run_id,
                latency_ms=result.latency_ms,
                model="none",
            )
        # Grounded QA via the QA chat service (search → pack → generate → cite).
        from geomemory.qa.chat_service import ChatService as QAChatService
        from geomemory.qa.llama_cpp_backend import LlamaCppBackend

        chat = QAChatService(
            _WorkspaceSearchAdapter(self, collections=collections),
            LlamaCppBackend(model_path),
        )
        answer = chat.ask(question, mode=mode, filters=filters)
        self._persist_answer(question, answer)
        return answer

    def _persist_answer(self, question: str, answer: QAResult) -> None:
        """Persist a QA exchange (conversation, turns, answer, citations)."""
        from geomemory.core.models import Answer, Conversation, Turn
        from geomemory.storage.repositories.conversation_repo import (
            ConversationRepository,
            TurnRepository,
        )

        conv = Conversation(
            workspace_id=self._workspace_id(),
            title=(question or "")[:80],
        )
        ConversationRepository(self.conn).create(conv)
        user_turn = Turn(conversation_id=conv.id, role="user", content=question)
        TurnRepository(self.conn).create(user_turn)
        assistant_turn = Turn(
            conversation_id=conv.id,
            role="assistant",
            content=answer.text,
            metadata={"abstained": answer.abstained},
        )
        TurnRepository(self.conn).create(assistant_turn)

        prompt_hash = hashlib.sha256((question or "").encode("utf-8")).hexdigest()
        answer_row = Answer(
            turn_id=assistant_turn.id,
            model=answer.model or "none",
            prompt_hash=prompt_hash,
            text=answer.text,
            abstained=answer.abstained,
        )
        self.conn.execute(
            "INSERT INTO answer "
            "(id, turn_id, model, prompt_hash, text, abstained, created_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                answer_row.id,
                answer_row.turn_id,
                answer_row.model,
                answer_row.prompt_hash,
                answer_row.text,
                1 if answer_row.abstained else 0,
                answer_row.created_at,
                json.dumps(answer_row.metadata),
            ),
        )
        for citation in answer.citations:
            self.conn.execute(
                "INSERT INTO citation (id, answer_id, segment_id, locator, claim_span, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    citation.id,
                    answer_row.id,
                    citation.segment_id,
                    json.dumps(citation.locator),
                    json.dumps(citation.claim_span) if citation.claim_span else None,
                    citation.created_at,
                ),
            )
        self.conn.commit()

    # ── Index ────────────────────────────────────────────────────────────────

    def build_index(self, space_id: str) -> None:
        """Build the retrieval index for a space.

        Embeds all segments (via the configured embedding model, or the
        offline hashing embedder) and persists a dense index under
        ``index_dir/<space_id>``. Already-embedded segments are skipped, so
        repeated calls are incremental.
        """
        from geomemory.services.index_service import IndexService

        service = IndexService(
            self.conn, self.index_dir, batch_size=self.settings.batch_size
        )
        service.build(space_id, model_path=self.settings.embedding_path)
        self._index_space = space_id

    def rebuild_index(self, space_id: str) -> None:
        """Rebuild the index for a space from SQLite source."""
        from geomemory.services.index_service import IndexService

        service = IndexService(
            self.conn, self.index_dir, batch_size=self.settings.batch_size
        )
        service.rebuild(space_id, model_path=self.settings.embedding_path)
        self._index_space = space_id

    # ── Feedback ────────────────────────────────────────────────────────────

    def record_feedback(self, event: FeedbackEvent) -> FeedbackEvent:
        """Record an immutable feedback event."""
        from geomemory.storage.repositories.feedback_repo import FeedbackRepository

        return FeedbackRepository(self.conn).create(event)

    def get_review_queue(self) -> list[DatasetExample]:
        """Return pending dataset examples for review."""
        from geomemory.storage.repositories.feedback_repo import DatasetExampleRepository

        return DatasetExampleRepository(self.conn).list_by_state("pending")

    def review_example(
        self, example_id: str, *, accept: bool, reviewer_id: str | None = None
    ) -> bool:
        """Accept or reject a pending dataset example. Returns True on change."""
        from geomemory.storage.repositories.feedback_repo import DatasetExampleRepository

        repo = DatasetExampleRepository(self.conn)
        current = repo.get(example_id)
        if current is None:
            return False
        target = "accepted" if accept else "rejected"
        if current.review_state == target:
            return False
        return repo.update_state(example_id, target, reviewer_id)
    def export_dataset(self, task_type: str, output_dir: str | Path) -> Path:
        """Export accepted examples for a task type to a JSONL file."""
        from geomemory.services.feedback_service import FeedbackService

        return FeedbackService(self.conn).export_dataset(task_type, output_dir)

    # ── Evaluation ──────────────────────────────────────────────────────────

    def run_benchmark(self, benchmark_path: str, config: str | None = None) -> BenchmarkResult:
        """Run a benchmark from a JSONL file."""
        from geomemory.eval.runner import BenchmarkRunner

        runner = BenchmarkRunner(self)
        return runner.run(benchmark_path, config)

    # ── Inspection ──────────────────────────────────────────────────────────

    def list_assets(self, collection_id: str | None = None) -> list[Asset]:
        """List assets, optionally filtered by collection."""
        from geomemory.storage.repositories.asset_repo import AssetRepository

        repo = AssetRepository(self.conn)
        if collection_id is None:
            return [a for a in repo.list_all() if a.deleted_at is None]
        return repo.get_by_collection(collection_id)

    def inspect(self, asset_id: str) -> AssetDetail:
        """Return a full inspection view of an asset."""
        asset = self._asset_by_id(asset_id)
        revision = self._revision_by_id(asset.current_revision_id) if asset.current_revision_id else None
        segments = self._segments_for_revision(asset.current_revision_id or "") or []
        scenes: list[Any] = []
        layers: list[Any] = []
        observations: list[Any] = []
        if revision is not None:
            from geomemory.storage.repositories.spatial_repo import (
                ObservationRepository,
                RasterSceneRepository,
                VectorLayerRepository,
            )

            scenes = RasterSceneRepository(self.conn).get_by_revision(revision.id)
            layers = VectorLayerRepository(self.conn).get_by_revision(revision.id)
            for scene in scenes:
                observations.extend(
                    ObservationRepository(self.conn).get_by_subject(scene.id)
                )
        return AssetDetail(
            asset=asset,
            revision=revision,
            collections=[self.get_collection(asset.collection_id)] if asset.collection_id else [],
            segments=segments,
            scenes=scenes,
            layers=layers,
            observations=observations,
        )

    # ── Overview stats ─────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return lightweight workspace statistics for dashboards.

        Includes collection/asset/segment counts, spatial index usage, index
        manifest state, feedback counts, and storage footprint. All values are
        JSON-serializable and derived from the workspace itself.
        """
        collections = self.list_collections()
        assets = [a for a in self.list_assets()]
        segments = 0
        revision_ids: set[str] = set()
        for asset in assets:
            if asset.current_revision_id:
                revision_ids.add(asset.current_revision_id)
        for rev_id in revision_ids:
            count = self.conn.execute(
                "SELECT COUNT(*) AS c FROM segment WHERE revision_id = ?", (rev_id,)
            ).fetchone()
            if count is not None:
                segments += int(count["c"])

        scene_count = 0
        vector_count = 0
        for rev_id in revision_ids:
            for table, column in (
                ("raster_scene", "revision_id"),
                ("vector_layer", "revision_id"),
            ):
                row = self.conn.execute(
                    f"SELECT COUNT(*) AS c FROM {table} WHERE {column} = ?", (rev_id,)
                ).fetchone()
                n = int(row["c"]) if row is not None else 0
                if table == "raster_scene":
                    scene_count += n
                else:
                    vector_count += n
        obs_row = self.conn.execute("SELECT COUNT(*) AS c FROM observation").fetchone()
        observation_count = int(obs_row["c"]) if obs_row is not None else 0

        from geomemory.storage.repositories.feedback_repo import (
            DatasetExampleRepository,
            FeedbackRepository,
        )

        feedback_count = FeedbackRepository(self.conn).count()
        pending_review = len(
            DatasetExampleRepository(self.conn).list_by_state("pending")
        )

        from geomemory.storage.repositories.spatial_repo import SpatialRepository

        spatial_entities = SpatialRepository(self.conn).count()

        index_manifest: dict[str, Any] | None = None
        try:
            from geomemory.index.manifest import load_manifest

            manifest = load_manifest(self.index_dir)
            index_manifest = manifest.model_dump(mode="json")
        except Exception:
            index_manifest = None

        db_bytes = self.db_path.stat().st_size if self.db_path.is_file() else 0
        objects_bytes = 0
        objects_dir = Path(self.path) / DEFAULT_OBJECTS_DIR
        if objects_dir.is_dir():
            for p in objects_dir.rglob("*"):
                if p.is_file():
                    objects_bytes += p.stat().st_size

        return {
            "collections": len(collections),
            "assets": len(assets),
            "segments": segments,
            "raster_scenes": scene_count,
            "vector_layers": vector_count,
            "observations": observation_count,
            "spatial_entities": spatial_entities,
            "feedback_events": feedback_count,
            "pending_review": pending_review,
            "index_manifest": index_manifest,
            "storage_bytes": db_bytes + objects_bytes,
            "db_bytes": db_bytes,
            "objects_bytes": objects_bytes,
            "settings": self.settings.model_dump(),
        }

    # ── Image search (experimental, vision embeddings) ─────────────────────

    def image_index(self) -> Any:
        """Return the persisted image index manager (empty when none exists)."""
        from geomemory.index.image_index import ImageIndex

        index_dir = self.index_dir / "image"
        if (index_dir / "manifest.json").is_file():
            try:
                return ImageIndex.load(index_dir)
            except (OSError, ValueError):
                return ImageIndex()
        return ImageIndex()

    def search_images(self, query_vector: Any, *, top_k: int = 10) -> list[dict[str, Any]]:
        """Search vision-embedded raster tiles by image vector (experimental)."""
        return self.image_index().search(query_vector, top_k=top_k)

    # ── Internal helpers ────────────────────────────────────────────────────

    def _workspace_id(self) -> str:
        row = self.conn.execute("SELECT id FROM workspace LIMIT 1").fetchone()
        if row is not None:
            return str(row["id"])
        # First access: register this workspace.
        ws = WorkspaceModel(name=self.settings.name, settings=self.settings.model_dump())
        self.conn.execute(
            "INSERT INTO workspace (id, name, settings, created_at) VALUES (?, ?, ?, ?)",
            (ws.id, ws.name, json.dumps(ws.settings), ws.created_at),
        )
        self.conn.commit()
        return ws.id

    def _asset_by_id(self, asset_id: str) -> Asset:
        from geomemory.storage.repositories.asset_repo import AssetRepository

        asset = AssetRepository(self.conn).get(asset_id)
        if asset is None or asset.deleted_at is not None:
            raise AssetNotFoundError(f"Asset not found: {asset_id}")
        return asset

    def _revision_by_id(self, revision_id: str) -> AssetRevision | None:
        from geomemory.storage.repositories.asset_repo import AssetRevisionRepository

        return AssetRevisionRepository(self.conn).get(revision_id)

    def _segments_for_revision(self, revision_id: str) -> list[Segment] | None:
        from geomemory.storage.repositories.segment_repo import SegmentRepository

        segments = SegmentRepository(self.conn).get_by_revision(revision_id)
        if not segments:
            return None
        return segments

    def _save_retrieval_run(self, run: RetrievalRun, results: list[dict[str, Any]]) -> None:
        self.conn.execute(
            "INSERT INTO retrieval_run (id, turn_id, query, query_plan, filters, config, candidates, results, latency_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, '[]', ?, ?, ?)",
            (
                run.id,
                run.turn_id,
                run.query,
                json.dumps(run.query_plan),
                json.dumps(run.filters),
                json.dumps(run.config),
                json.dumps(results),
                run.latency_ms,
                run.created_at,
            ),
        )
        self.conn.commit()


# ──────────────────────────────────────────────────────────────────────────────
# Public API class
# ──────────────────────────────────────────────────────────────────────────────


class _WorkspaceSearchAdapter(SearchService):
    """Adapt :meth:`Workspace.search` to the SearchService interface used by QA."""

    def __init__(self, workspace: Workspace, *, collections: list[str] | None = None) -> None:
        super().__init__([])
        self._workspace = workspace
        self._collections = collections

    def search(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        top_k: int = 20,
        top_n: int = 5,
        filters: SearchFilters | None = None,
    ) -> SearchResult:
        return self._workspace.search(
            query,
            mode=mode,
            top_k=top_k,
            top_n=top_n,
            collections=self._collections,
        )


class GeoMemory(Workspace):
    """Public entry point for the GeoMemory library.

    Usage::

        memory = GeoMemory.open("./workspace")
        collection = memory.create_collection("papers")
        job = memory.ingest("paper.pdf", collection_id=collection.id)
        results = memory.search("vegetation indices")
        answer = memory.ask("Which indices detect crop stress?")
    """

    @classmethod
    def open(cls, path: str | Path) -> GeoMemory:
        """Open an existing workspace."""
        return cls(path, create=False)

    @classmethod
    def create(cls, path: str | Path, config: WorkspaceConfig | None = None) -> GeoMemory:
        """Create a new workspace."""
        return cls(path, create=True, config=config)


# ──────────────────────────────────────────────────────────────────────────────
# Module-level helpers
# ──────────────────────────────────────────────────────────────────────────────


def _detect_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    table = {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".py": "text/x-python",
        ".js": "text/javascript",
        ".ipynb": "application/x-ipynb+json",
        ".csv": "text/csv",
        ".geojson": "application/geo+json",
        ".gpkg": "application/geo+json",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }
    return table.get(suffix, "application/octet-stream")


def _kind_for_mime(mime_type: str) -> str:
    if mime_type.startswith("text/"):
        return "document"
    if mime_type in ("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
        return "document"
    if mime_type in ("text/x-python", "text/javascript"):
        return "code"
    if mime_type in ("image/tiff", "image/geotiff"):
        return "raster"
    if mime_type == "application/geo+json":
        return "vector"
    if mime_type == "text/csv":
        return "table"
    return "document"


def _chunk_document(
    raw: bytes,
    mime_type: str,
    source_path: str,
    *,
    parser: str | None = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[dict[str, Any]]:
    """Parse raw bytes into a simple text representation and split into chunks.

    Structural chunking (header-first) is implemented in the ingest layer;
    this core fallback performs fixed-size token-approximation chunking so the
    workspace is usable standalone.
    """
    text = raw.decode("utf-8", errors="replace")
    # Simple header-aware splitting: split on newline, accumulate to size.
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[dict[str, Any]] = []
    current: list[str] = []
    current_tokens = 0
    approx_per_char = 0.25  # rough token estimate

    def flush() -> None:
        nonlocal current, current_tokens
        if current:
            joined = "\n".join(current)
            chunks.append(
                {
                    "text": joined,
                    "segment_type": "paragraph",
                    "locator": {"file": source_path},
                }
            )
            current = []
            current_tokens = 0

    for para in paragraphs:
        para_tokens = max(1, int(len(para) * approx_per_char))
        if current_tokens + para_tokens > chunk_size and current:
            flush()
        current.append(para)
        current_tokens += para_tokens
    flush()

    if not chunks and text.strip():
        chunks.append(
            {
                "text": text.strip()[:4000],
                "segment_type": "paragraph",
                "locator": {"file": source_path},
            }
        )
    return chunks


_FTS_TERM_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


def _rrf_fuse(groups: list[list[SearchHit]], *, top_n: int, k: int = 60) -> list[SearchHit]:
    """Reciprocal Rank Fusion over multiple ranked lists."""
    scores: dict[str, float] = {}
    by_id: dict[str, SearchHit] = {}
    seen: dict[str, set[int]] = {}
    for group_idx, group in enumerate(groups):
        for rank, hit in enumerate(group):
            key = hit.id
            if key not in by_id:
                by_id[key] = hit
                seen[key] = set()
            if group_idx not in seen[key]:
                seen[key].add(group_idx)
                scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    for key, score in ranked:
        by_id[key].score = score
    return [by_id[k] for k, _ in ranked]


def _hit_sensor(hit: SearchHit) -> str | None:
    """Return the sensor recorded on a hit, if any."""
    direct = hit.metadata.get("sensor")
    if direct:
        return str(direct)
    spatial = hit.metadata.get("spatial")
    if isinstance(spatial, dict):
        sensor = spatial.get("sensor")
        if sensor:
            return str(sensor)
    return None


def _job_completed(job_type: str, result: dict[str, Any]) -> Job:
    return Job(
        type=job_type,
        state="completed",
        progress=1.0,
        result=result,
    )

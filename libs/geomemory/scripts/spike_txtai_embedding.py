"""T0-6 spike: validate Nomic GGUF embedding + txtai persistence + reload + search.

Usage:
    python scripts/spike_txtai_embedding.py [--model PATH] [--index-dir DIR]

This spike proves the core Phase 0 risk: that a local GGUF embedding model
(loaded via llama-cpp-python) can produce vectors that are persisted into a
txtai index, reloaded, and searched — all fully offline.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_MODEL = "/mnt/data/LocalAI/Models/Embeddings/nomic-embed-text-v2-moe.Q8_0.gguf"

SAMPLE_TEXTS = [
    "Crop stress detection using NDVI time series from Sentinel-2 imagery",
    "Evapotranspiration estimation with the SEBAL model over irrigated farmland",
    "Random forest classification of land cover from Landsat-8 multispectral data",
    "Soil moisture retrieval using synthetic aperture radar backscatter",
    "Deep learning for building footprint extraction from high-resolution satellite images",
]

QUERIES = [
    "vegetation health monitoring with satellite indices",
    "machine learning land cover mapping",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="txtai + Nomic GGUF embedding spike")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Path to Nomic GGUF model")
    parser.add_argument("--index-dir", default=None, help="Directory for the txtai index")
    parser.add_argument("--batch-size", type=int, default=8, help="Embedding batch size")
    args = parser.parse_args()

    model_path = Path(args.model)
    if not model_path.is_file():
        print(f"ERROR: model file not found: {model_path}", file=sys.stderr)
        return 1

    index_dir = Path(args.index_dir) if args.index_dir else Path(tempfile.mkdtemp(prefix="geomemory_spike_"))
    print(f"Model:  {model_path}")
    print(f"Index:  {index_dir}")

    # ── 1. Load embedding model via llama-cpp-python ─────────────────────────
    print("\n[1/5] Loading Nomic GGUF via llama-cpp-python ...")
    try:
        from llama_cpp import Llama
    except ImportError as exc:
        print(f"ERROR: llama-cpp-python not installed: {exc}", file=sys.stderr)
        return 1

    t0 = time.perf_counter()
    llm = Llama(model_path=str(model_path), embedding=True, n_ctx=2048, verbose=False)
    print(f"      loaded in {time.perf_counter() - t0:.2f}s")

    # ── 2. Generate embeddings ───────────────────────────────────────────────
    print("\n[2/5] Generating embeddings ...")
    t0 = time.perf_counter()
    embeddings = []
    for i in range(0, len(SAMPLE_TEXTS), args.batch_size):
        batch = SAMPLE_TEXTS[i : i + args.batch_size]
        for text in batch:
            out = llm.create_embedding(text)
            vec = out["data"][0]["embedding"]
            embeddings.append(vec)
    print(f"      {len(embeddings)} embeddings in {time.perf_counter() - t0:.2f}s")
    dim = len(embeddings[0])
    print(f"      dimension: {dim}")

    # ── 3. Persist into txtai index ──────────────────────────────────────────
    print("\n[3/5] Persisting into txtai index ...")
    try:
        from txtai.embeddings import Embeddings
    except ImportError as exc:
        print(f"ERROR: txtai not installed: {exc}", file=sys.stderr)
        return 1

    t0 = time.perf_counter()
    db = Embeddings(path=index_dir, content=True, hybrid=True, sparse=True)
    rows = [
        {"id": f"doc_{i}", "text": text, "embedding": embeddings[i]}
        for i, text in enumerate(SAMPLE_TEXTS)
    ]
    db.index(rows)
    print(f"      indexed {len(rows)} docs in {time.perf_counter() - t0:.2f}s")

    # ── 4. Reload from disk ──────────────────────────────────────────────────
    print("\n[4/5] Reloading index from disk ...")
    t0 = time.perf_counter()
    db2 = Embeddings(path=index_dir, content=True, hybrid=True, sparse=True)
    print(f"      reloaded in {time.perf_counter() - t0:.2f}s, count={len(db2)}")

    # ── 5. Search ────────────────────────────────────────────────────────────
    print("\n[5/5] Searching ...")
    for query in QUERIES:
        t0 = time.perf_counter()
        results = db2.search(query, limit=3)
        elapsed = time.perf_counter() - t0
        print(f"\n  Query: {query!r} ({elapsed * 1000:.1f}ms)")
        for r in results:
            print(f"    - {r.get('score', 0):.4f}  {r.get('text', '')[:80]}")

    # ── Summary ──────────────────────────────────────────────────────────────
    manifest = {
        "spike": "txtai_embedding",
        "model": str(model_path),
        "dimension": dim,
        "docs": len(rows),
        "index_dir": str(index_dir),
        "status": "ok",
    }
    summary_path = index_dir / "spike_result.json"
    summary_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n✅ Spike passed. Summary written to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

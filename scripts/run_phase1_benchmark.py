"""Run the Phase 1 benchmark against a workspace built from golden fixtures.

Usage:
    python scripts/run_phase1_benchmark.py [--workspace DIR] [--out DIR]

The script ingests the golden fixtures into a temporary workspace, resolves
each benchmark item's ``gold_ids`` by substring match against the stored
segments, then runs retrieval and QA benchmarks.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path

from geomemory import GeoMemory
from geomemory.eval.runner import BenchmarkRunner
from geomemory.eval.reporter import json_report

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "golden" / "fixtures"
RETRIEVAL_BENCH = ROOT / "benchmarks" / "retrieval" / "phase1_benchmark.jsonl"
QA_BENCH = ROOT / "benchmarks" / "qa" / "phase1_benchmark.jsonl"


def _resolve_gold_ids(conn: sqlite3.Connection, substring: str) -> list[str]:
    """Return segment ids whose text contains the substring."""
    rows = conn.execute(
        "SELECT id FROM segment WHERE instr(text, ?) > 0 LIMIT 5", (substring,)
    ).fetchall()
    return [str(r["id"]) for r in rows]


def _resolve_benchmark(path: Path, conn: sqlite3.Connection) -> Path:
    """Return a temp benchmark file with gold_ids resolved from the workspace."""
    out_lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        substring = item.get("metadata", {}).get("gold_substring")
        if substring:
            item["gold_ids"] = _resolve_gold_ids(conn, substring)
        out_lines.append(json.dumps(item, ensure_ascii=False))

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=path.suffix, delete=False, encoding="utf-8"
    )
    tmp.write("\n".join(out_lines) + "\n")
    tmp.close()
    return Path(tmp.name)


def _ingest_fixtures(ws: GeoMemory) -> None:
    col = ws.create_collection("phase1_golden")
    for fixture in sorted(FIXTURES.glob("*")):
        if fixture.suffix in (".pdf", ".docx"):
            continue  # optional binary parsers are not required
        ws.ingest(fixture, collection_id=col.id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", "-w", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    tmp = tempfile.TemporaryDirectory(prefix="geomemory-bench-")
    ws = GeoMemory.create(args.workspace or Path(tmp.name) / "ws")
    try:
        _ingest_fixtures(ws)
        retrieval_file = _resolve_benchmark(RETRIEVAL_BENCH, ws.conn)
        qa_file = _resolve_benchmark(QA_BENCH, ws.conn)

        runner = BenchmarkRunner(ws)
        results = {
            "retrieval": runner.run(str(retrieval_file)),
            "qa": runner.run(str(qa_file)),
        }

        for name, result in results.items():
            print(json_report(result.name, result.metrics))
            print(result.report)

        if args.out is not None:
            args.out.mkdir(parents=True, exist_ok=True)
            for name, result in results.items():
                (args.out / f"{name}_result.json").write_text(
                    json_report(result.name, result.metrics), encoding="utf-8"
                )
    finally:
        ws.close()
        tmp.cleanup()


if __name__ == "__main__":
    main()

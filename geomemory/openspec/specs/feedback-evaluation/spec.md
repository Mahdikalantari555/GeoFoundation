# Feedback & Evaluation — As-Is Specification

Baseline extracted from current implementation. Describes existing behavior only.

## Requirements

### Requirement: Feedback event capture
The system SHALL record raw feedback events (target type/id, actor, label, payload) append-only.

#### Scenario: Record rating
- **WHEN** an answer-rating or source-relevance event is recorded via the facade
- **THEN** a `feedback_event` row persists with timestamp

### Requirement: Dataset example construction
Feedback SHALL be convertible into dataset examples with task typing and source linkage; duplicate examples SHALL be grouped/deduplicated before entering review.

#### Scenario: Build + dedup
- **WHEN** equivalent feedback arrives twice
- **THEN** duplicate grouping collapses them so the queue holds one candidate

### Requirement: Review workflow
Dataset examples SHALL move through states `pending → accepted | rejected` with reviewer id and timestamp recorded.

#### Scenario: Accept example
- **WHEN** `review_example(id, accept=True)` runs
- **THEN** state becomes accepted and it becomes exportable

### Requirement: Dataset export
Accepted examples SHALL export per task type — `rag_eval`, `qa_eval`, `sft`, `preference` — as JSONL plus a dataset card describing provenance.

#### Scenario: Export rag_eval
- **WHEN** `export_dataset("rag_eval", out_dir)` runs on accepted examples
- **THEN** JSONL rows and card metadata appear in the output directory

### Requirement: Retrieval metrics
The eval package SHALL compute recall@k, precision@k, MRR@k, and nDCG@k over labeled benchmark items.

#### Scenario: Benchmark run
- **WHEN** `geomemory eval run BENCHMARK.jsonl` executes
- **THEN** aggregated retrieval metrics print/emit in json or markdown

### Requirement: QA metrics
The eval package SHALL measure abstention accuracy/rate, citation correctness, and a faithfulness proxy for QA benchmarks.

#### Scenario: QA aggregation
- **WHEN** benchmark items include expected abstentions/citations
- **THEN** corresponding metric groups aggregate and report alongside retrieval metrics

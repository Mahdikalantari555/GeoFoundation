# Grounded QA — As-Is Specification

Baseline extracted from current implementation. Describes existing behavior only.

## Requirements

### Requirement: Grounded answering
The system SHALL answer questions using retrieved workspace evidence via a prompt appropriate to the selected mode (`grounded_qa`, `research`, `code`).

#### Scenario: Answer with evidence
- **WHEN** `ask(question)` is called on a workspace with indexed content and a configured LLM backend
- **THEN** the returned `QAResult.text` is generated from packed context and carries citations

### Requirement: Citations
Answers SHALL map inline `[n]` markers to source segments, validated against retrieved hits; each citation persists with locator and optional claim span.

#### Scenario: Citation mapping
- **WHEN** the model emits `[2]` referring to context item 2
- **THEN** a citation row links answer → segment with locator metadata

### Requirement: Abstention
The system SHALL detect insufficient-evidence answers and flag abstention instead of presenting ungrounded content as fact.

#### Scenario: No model configured
- **WHEN** NullBackend is active (no GGUF configured)
- **THEN** generation abstains rather than fabricating content

### Requirement: Conversation persistence
Each ask SHALL record conversation, turn(s), answer (model id, prompt_hash, abstained flag), and citations.

#### Scenario: Audit trail
- **WHEN** any QA exchange completes
- **THEN** turn/answer/citation rows allow full replay of question → evidence → response

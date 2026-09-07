## Purpose
Ensure the web app never silently fails: ingest, agent chat, doctor, and workspace surfaces all have explicit loading/empty/error states, error banners with recovery actions, and no `[object Object]` rendering.

## ADDED Requirements

### Requirement: No silent failures — global error surfacing
The app SHALL surface every 4xx/5xx, network failure, SSE disconnect, and job failure as a visible banner/toast with `code` + `message` + retry action, never as a blank screen or console-only error.

#### Scenario: Global boundary
- **WHEN** any page throws or any `openapi-fetch` call returns non-2xx
- **THEN** an `ErrorBoundary` / query `onError` renders an alert banner with the envelope's `code` and `message` and a retry button that reissues the request

#### Scenario: SSE disconnect
- **WHEN** the `GET /api/v1/events` or `POST /api/v1/agent/chat` stream disconnects or emits `error`
- **THEN** the UI shows a reconnecting/error banner (not silent disappearance) and offers retry

### Requirement: Ingest page explicit states
The Ingest page SHALL show queued→running→done/error per job, dedup (`skipped:true`) banner, collection-missing and workspace-closed guards, and field-level validation (unsupported format, 413) with the accepted types list.

#### Scenario: Duplicate upload
- **WHEN** a file with previously ingested SHA-256 is uploaded
- **THEN** a dedup banner appears ("Already ingested — skipped") and `segment_count` is not incremented

#### Scenario: Upload without collection
- **WHEN** user attempts upload with no collection selected
- **THEN** the submit button is disabled and a helper text "Select a collection" is shown; if bypassed, server 422 is rendered as a banner

### Requirement: Agent chat explicit states
Agent Chat SHALL stream `thinking` → tool timeline → messages with citation chips, and on `error`/`guardrail`/`abstention` SHALL render a card with `code/reason` and a retry/abort control; aborted streams SHALL show "Cancelled" not silent.

#### Scenario: Chat without workspace
- **WHEN** the user opens Chat with no workspace open
- **THEN** a `409 agent_not_ready` card appears with action "Open workspace" linking to workspace switcher

### Requirement: Doctor rendering without [object Object]
Doctor SHALL render `checks` as flat rows (boolean→badge, string/number→mono text) and render `diagnostics.{llm,qdrant,pdf_parser,vision}` in dedicated sections with typed fields, never calling `String(object)`.

#### Scenario: No object string
- **WHEN** Doctor is viewed with a workspace open
- **THEN** the DOM contains no text "`[object Object]`" and the diagnostics sections show `provider`, `model_id`, `key_configured`, `qdrant.reachable`, `pdf_parser.resolved`, `vision.checkpoint_exists` as primitives/badges

### Requirement: Workspace default UX
The workspace switcher SHALL offer `Workspaces` (resolved `GEOFOND_WORKSPACE`) as default, auto-create it, and display the resolved absolute path. Closing/no workspace SHALL show "No workspace open" with create/open affordance.

#### Scenario: First run no workspace
- **WHEN** the app loads with no workspace open
- **THEN** the header pill shows "workspace: closed" and the Overview empty state offers "Create in default Workspaces/"

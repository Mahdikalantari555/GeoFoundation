const BASE = '/api/v1'

export interface DoctorReport {
  environment: Record<string, unknown>
  workspace: Record<string, unknown> & { checks?: Record<string, unknown>; ok?: boolean; closed?: boolean }
  workspace_open: Record<string, unknown> & { checks?: Record<string, unknown>; ok?: boolean; closed?: boolean }
  embedding: {
    hub_count: number
    downloaded: number
    active_backend: string | null
    active_model: string | null
    active_space_id: string | null
    sqlite_vec?: unknown
  }
  diagnostics?: {
    llm?: Record<string, unknown>
    qdrant?: Record<string, unknown>
    pdf_parser?: Record<string, unknown>
    vision?: Record<string, unknown>
    embedding?: Record<string, unknown>
    sqlite_vec?: Record<string, unknown>
  }
  resolved_workspace_root?: string
}

export interface LLMReport {
  provider: string | null
  key_env: string
  key_configured?: boolean
  key_set?: boolean
  base_url?: string | null
  api_base_url?: string | null
  context_window?: number
  model_id?: string
}

export interface EvalResult {
  name: string
  metrics: Record<string, unknown>
}

export const opsApi = {
  doctor: () =>
    fetch(`${BASE}/doctor`).then((r) => {
      if (!r.ok) throw new Error(`Doctor failed: ${r.status}`)
      return r.json() as Promise<DoctorReport>
    }),

  doctorLlm: () =>
    fetch(`${BASE}/doctor/llm`).then((r) => {
      if (!r.ok) throw new Error(`LLM probe failed: ${r.status}`)
      return r.json() as Promise<LLMReport>
    }),

  buildIndex: (spaceId = 'text.nomic.v1') =>
    fetch(`${BASE}/index/build?space_id=${encodeURIComponent(spaceId)}`, {
      method: 'POST',
    }).then((r) => {
      if (!r.ok) throw new Error(`Index build failed: ${r.status}`)
      return r.json() as Promise<{ status: string; space_id: string }>
    }),

  rebuildIndex: (spaceId = 'text.nomic.v1') =>
    fetch(`${BASE}/index/rebuild?space_id=${encodeURIComponent(spaceId)}`, {
      method: 'POST',
    }).then((r) => {
      if (!r.ok) throw new Error(`Index rebuild failed: ${r.status}`)
      return r.json() as Promise<{ status: string; space_id: string }>
    }),

  runEval: (benchmarkPath: string, config?: string) =>
    fetch(`${BASE}/eval/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ benchmark_path: benchmarkPath, config }),
    }).then((r) => {
      if (!r.ok) throw new Error(`Eval failed: ${r.status}`)
      return r.json() as Promise<EvalResult>
    }),

  exportFeedback: (taskType: string) =>
    fetch(`${BASE}/feedback/export?task_type=${encodeURIComponent(taskType)}`).then(
      (r) => {
        if (!r.ok) throw new Error(`Export failed: ${r.status}`)
        return r
      }
    ),

  listCandidates: (state?: string) =>
    fetch(`${BASE}/feedback/candidates${state ? `?state=${encodeURIComponent(state)}` : ''}`).then((r) => {
      if (!r.ok) throw new Error(`List candidates failed: ${r.status}`)
      return r.json() as Promise<unknown[]>
    }),

  reviewCandidate: (id: string, new_state: string, reviewer_id?: string, note?: string) =>
    fetch(`${BASE}/feedback/candidates/${encodeURIComponent(id)}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_state, reviewer_id, note }),
    }).then((r) => {
      if (!r.ok) throw new Error(`Review failed: ${r.status}`)
      return r.json()
    }),

  listProposals: (status?: string) =>
    fetch(`${BASE}/feedback/proposals${status ? `?status=${encodeURIComponent(status)}` : ''}`).then((r) => {
      if (!r.ok) throw new Error(`List proposals failed: ${r.status}`)
      return r.json() as Promise<unknown[]>
    }),

  approveProposal: (id: string, reviewer_id?: string, note?: string) =>
    fetch(`${BASE}/feedback/proposals/${encodeURIComponent(id)}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reviewer_id, note }),
    }).then((r) => {
      if (!r.ok) throw new Error(`Approve failed: ${r.status}`)
      return r.json()
    }),

  rejectProposal: (id: string, reviewer_id?: string, note?: string) =>
    fetch(`${BASE}/feedback/proposals/${encodeURIComponent(id)}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reviewer_id, note }),
    }).then((r) => {
      if (!r.ok) throw new Error(`Reject failed: ${r.status}`)
      return r.json()
    }),
}

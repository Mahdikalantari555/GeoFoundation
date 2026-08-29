const BASE = '/api/v1'

export interface DoctorReport {
  environment: Record<string, unknown>
  workspace: Record<string, unknown>
  workspace_open: Record<string, unknown>
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
}

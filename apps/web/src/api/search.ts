import { request } from './client'

// ── Types (mirror the gateway /search, /ask, /feedback contracts) ───────────

export type SearchMode = 'sparse' | 'dense' | 'hybrid'
export type AskMode = 'grounded_qa' | 'research' | 'code'

export type SpatialFilter = {
  op?: 'intersects' | 'within' | 'contains' | 'distance_lte'
  geometry_id?: string | null
  bbox?: [number, number, number, number] // min_lon, min_lat, max_lon, max_lat
  distance_m?: number | null
}

export type TemporalFilter = {
  field?: 'acquired_at' | 'observed_at' | 'published_at' | 'ingested_at'
  from?: string | null
  to?: string | null
}

export type QueryPlan = {
  intent: string
  mode: string
  spaces: string[]
  top_k: number
  top_n: number
  filters?: Record<string, unknown> | null
}

export type SearchHit = {
  id: string
  score: number
  sparse_score: number | null
  dense_score: number | null
  metadata: Record<string, unknown>
  text: string
  locator: Record<string, unknown>
}

export type SearchResult = {
  query: string
  query_plan: QueryPlan
  hits: SearchHit[]
  total_hits: number
  latency_ms: number | null
  retrieval_run_id: string | null
}

export type Citation = {
  id: string
  answer_id: string
  segment_id: string
  locator: Record<string, unknown>
  claim_span?: { start: number; end: number } | null
}

export type QAResult = {
  text: string
  citations: Citation[]
  abstained: boolean
  abstention_reason: string | null
  sources: SearchHit[]
  retrieval_run_id: string | null
  latency_ms: number | null
  model: string
}

export type FeedbackEvent = {
  id: string
  target_type: string
  target_id: string
  actor: string
  label: string
  payload: Record<string, unknown>
  created_at?: string
}

export type SearchBody = {
  query: string
  mode: SearchMode
  top_n?: number
  collections?: string[] | null
  sensor?: string[] | null
  spatial?: SpatialFilter | null
  temporal?: TemporalFilter | null
}

export type AskBody = {
  question: string
  mode?: AskMode
  collections?: string[] | null
  sensor?: string[] | null
  spatial?: SpatialFilter | null
  temporal?: TemporalFilter | null
}

export type FeedbackBody = {
  target_type: 'answer' | 'retrieval_run' | 'segment' | 'citation'
  target_id: string
  label: string
  actor?: string
  payload?: Record<string, unknown>
}

// ── API ──────────────────────────────────────────────────────────────────────

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: JSON.stringify(body) })
}

export const searchApi = {
  run: (body: SearchBody) => post<SearchResult>('/search', body),
}

export const askApi = {
  ask: (body: AskBody) => post<QAResult>('/ask', body),
}

export const feedbackApi = {
  record: (body: FeedbackBody) => post<FeedbackEvent>('/feedback', body),
}

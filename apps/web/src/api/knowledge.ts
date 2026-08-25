import { ApiError, type ApiErrorBody } from './client'

const BASE = '/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    ...init,
  })
  if (!resp.ok) {
    let parsed: unknown = null
    try {
      parsed = await resp.json()
    } catch {
      /* non-JSON error body */
    }
    const err = (parsed as ApiErrorBody | null)?.error
    throw new ApiError(err ?? { code: 'http_error', message: resp.statusText })
  }
  return (await resp.json()) as T
}

export type Collection = {
  id: string
  workspace_id: string
  name: string
  description: string | null
  created_at?: string
  archived?: boolean | null
}

export type Job = {
  id: string
  type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  result?: Record<string, unknown> | null
  error?: string | null
}

export type Asset = {
  id: string
  collection_id: string
  kind: string
  title: string
  current_revision_id?: string | null
  created_at?: string
  metadata?: Record<string, unknown> | null
}

export type AssetDetail = {
  asset: Asset
  revision?: Record<string, unknown> | null
  segments?: Array<Record<string, unknown>>
  scenes?: Array<Record<string, unknown>>
  layers?: Array<Record<string, unknown>>
  observations?: Array<Record<string, unknown>>
}

export type IngestResult = {
  asset_id?: string
  revision_id?: string
  segment_count?: number
  skipped?: boolean
  reason?: string
  error?: string
  job_type?: string
}

export const collectionsApi = {
  list: () => request<Collection[]>('/collections'),
  create: (body: { name: string; description?: string }) =>
    request<Collection>('/collections', { method: 'POST', body: JSON.stringify(body) }),
  get: (id: string) => request<Collection>(`/collections/${id}`),
  archive: (id: string) =>
    request<{ archived: boolean; id: string }>(`/collections/${id}`, { method: 'DELETE' }),
}

export const ingestApi = {
  file: (file: File, collectionId: string, indexAfter: boolean, parser?: string) => {
    const form = new FormData()
    form.append('file', file)
    form.append('collection_id', collectionId)
    form.append('index_after', String(indexAfter))
    if (parser) form.append('parser', parser)
    return request<{ job_id: string; status: string }>('/ingest', {
      method: 'POST',
      body: form,
    })
  },
  bytes: (body: {
    filename: string
    data_base64: string
    collection_id: string
    index_after: boolean
  }) =>
    request<{ job_id: string; status: string }>('/ingest/bytes', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}

export const assetsApi = {
  list: (collectionId?: string) =>
    request<Asset[]>(`/assets${collectionId ? `?collection_id=${encodeURIComponent(collectionId)}` : ''}`),
  inspect: (id: string) => request<AssetDetail>(`/assets/${id}`),
}

export const jobsApi = {
  get: (id: string) => request<Job>(`/jobs/${id}`),
}

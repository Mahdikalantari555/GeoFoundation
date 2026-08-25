import type { components } from './schema'
import { ApiError, type ApiErrorBody } from './client'

export type CreateWorkspaceRequest = components['schemas']['CreateWorkspaceRequest']
export type OpenWorkspaceRequest = components['schemas']['OpenWorkspaceRequest']
export type UpdateSettingsRequest = components['schemas']['UpdateSettingsRequest']

/** Mirrors geomemory WorkspaceSettings (returned as inline JSON, not a named schema). */
export type WorkspaceSettings = {
  name: string
  language: string | null
  offline: boolean
  model_path: string | null
  embedding_path: string | null
  vision_path: string | null
  default_collection: string | null
  index_dir: string
  objects_dir: string
  logs_dir: string
  batch_size: number
  thread_count: number
  llm_provider: string | null
  llm_api_base_url: string | null
  llm_api_key_env: string
  llm_model_id: string
  llm_context_window: number
  embedding_backend: string
  st_model_name: string
  vector_backend: string
  qdrant_url: string | null
  qdrant_api_key: string | null
  pdf_parser: string
}

export type WorkspaceStatus = {
  status: 'open' | 'closed'
  path: string | null
  settings: WorkspaceSettings | null
}

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

export const workspaceApi = {
  get: () => request<WorkspaceStatus>('/workspace'),
  create: (body: CreateWorkspaceRequest) =>
    request<{ status: string; path: string; settings: WorkspaceSettings }>(
      '/workspace/create',
      { method: 'POST', body: JSON.stringify(body) }
    ),
  open: (body: OpenWorkspaceRequest) =>
    request<{ status: string; path: string; settings: WorkspaceSettings }>(
      '/workspace/open',
      { method: 'POST', body: JSON.stringify(body) }
    ),
  close: () => request<{ status: string }>('/workspace/close', { method: 'POST' }),
  stats: () => request<Record<string, unknown>>('/workspace/stats'),
  updateSettings: (body: UpdateSettingsRequest) =>
    request<WorkspaceSettings>('/workspace/settings', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
}

import type { components } from './schema'

export type HealthWorkspace = components['schemas']['HealthWorkspace']
export type HealthLLM = components['schemas']['HealthLLM']
export type Health = components['schemas']['HealthResponse']

export type ApiErrorBody = {
  error: { code: string; message: string; detail?: unknown }
}

const BASE = import.meta.env.DEV ? '/api/v1' : '/api/v1'

export class ApiError extends Error {
  code: string
  detail?: unknown
  status: number
  requestId?: string

  constructor(body: ApiErrorBody['error'], status: number, requestId?: string) {
    super(body.message)
    this.code = body.code
    this.detail = body.detail
    this.status = status
    this.requestId = requestId
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
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
    const rid = resp.headers.get('X-Request-ID') ?? undefined
    throw new ApiError(err ?? { code: 'http_error', message: resp.statusText }, resp.status, rid)
  }
  return (await resp.json()) as T
}

export const api = {
  health: () => request<Health>('/health'),
}

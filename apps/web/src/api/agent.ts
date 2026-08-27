import { request } from './client'

// ── Types ────────────────────────────────────────────────────────────────────

export type AgentTool = {
  name: string
  description: string
  params: Record<string, unknown>
  returns: string
  timeout_s: number
  cacheable: boolean
}

export type ConversationSummary = {
  id: string
  title: string
  created_at: string
}

export type Turn = {
  id: string
  role: string
  content: string
  metadata: Record<string, unknown>
}

export type ToolRun = {
  id: string
  tool: string
  args_json: string
  status: string
  latency_ms: number | null
  error: string | null
  from_cache: number
  created_at: string
}

export type Conversation = {
  id: string
  title: string
  created_at: string
}

export type PlaybookSummary = {
  name: string
  version: number
  triggers: string[]
  params: Record<string, unknown>
  steps: { tool: string; args: Record<string, unknown> }[]
  valid: boolean
  problems: string[]
  source_path: string | null
}

export type FileEntry = {
  path: string
  size: number
  modified: number
}

// ── API ───────────────────────────────────────────────────────────────────────

export const agentApi = {
  listTools: () => request<{ tools: AgentTool[] }>('/agent/tools'),

  listConversations: () =>
    request<{ conversations: ConversationSummary[] }>('/agent/conversations'),

  getConversation: (id: string) =>
    request<{
      conversation: Conversation
      turns: Turn[]
      tool_runs: ToolRun[]
    }>(`/agent/conversations/${id}`),

  listPlaybooks: () =>
    request<{ playbooks: PlaybookSummary[] }>('/agent/playbooks'),

  getPlaybook: (name: string) =>
    request<PlaybookSummary & { content: string }>(`/agent/playbooks/${name}`),

  runPlaybook: (name: string, params: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/agent/playbooks/${name}/run`, {
      method: 'POST',
      body: JSON.stringify({ params }),
    }),

  savePlaybook: (name: string, content: string) =>
    request<{ saved: string; name: string }>('/agent/playbooks/save', {
      method: 'POST',
      body: JSON.stringify({ name, content }),
    }),

  listFiles: (pattern: string = 'runs/**/*') =>
    request<{ files: FileEntry[]; pattern: string }>(
      `/agent/files/list?pattern=${encodeURIComponent(pattern)}`
    ),

  downloadUrl: (path: string) =>
    `/api/v1/agent/files/download?path=${encodeURIComponent(path)}`,

  previewUrl: (path: string) =>
    `/api/v1/agent/files/preview?path=${encodeURIComponent(path)}`,
}

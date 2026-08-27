import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  workspaceApi,
  type CreateWorkspaceRequest,
  type OpenWorkspaceRequest,
  type UpdateSettingsRequest,
  type WorkspaceSettings,
  type WorkspaceStatus,
} from '@/api/workspace'

export const workspaceKeys = {
  status: ['workspace'] as const,
  stats: ['workspace', 'stats'] as const,
}

export function useWorkspace() {
  return useQuery<WorkspaceStatus>({ queryKey: workspaceKeys.status, queryFn: workspaceApi.get })
}

export function useWorkspaceStats() {
  const { data: ws } = useWorkspace()
  return useQuery({
    queryKey: workspaceKeys.stats,
    queryFn: workspaceApi.stats,
    enabled: ws?.status === 'open',
  })
}

export function useCreateWorkspace() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateWorkspaceRequest) => workspaceApi.create(body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: workspaceKeys.status }),
  })
}

export function useOpenWorkspace() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: OpenWorkspaceRequest) => workspaceApi.open(body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: workspaceKeys.status }),
  })
}

export function useCloseWorkspace() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => workspaceApi.close(),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: workspaceKeys.status })
      void qc.invalidateQueries({ queryKey: workspaceKeys.stats })
    },
  })
}

export function useUpdateSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateSettingsRequest) => workspaceApi.updateSettings(body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: workspaceKeys.status }),
  })
}

export type { WorkspaceSettings }

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  modelsApi,
  workspaceApi,
  type EmbeddingModel,
  type ModelDownloadResponse,
} from '@/api/workspace'
import type { UpdateSettingsRequest } from '@/api/workspace'

export const modelKeys = {
  list: ['models'] as const,
  status: (id: string) => ['models', id] as const,
}

export function useModels() {
  return useQuery<EmbeddingModel[]>({ queryKey: modelKeys.list, queryFn: modelsApi.list })
}

export function useModelStatus(modelId: string, enabled = true) {
  return useQuery({
    queryKey: modelKeys.status(modelId),
    queryFn: () => modelsApi.status(modelId),
    enabled,
  })
}

export function useDownloadModel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { model_name: string; backend: 'st' | 'onnx' }) =>
      modelsApi.download(body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: modelKeys.list }),
  })
}

export function useUpdateSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateSettingsRequest) => workspaceApi.updateSettings(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['workspace'] })
      void qc.invalidateQueries({ queryKey: modelKeys.list })
    },
  })
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${units[i]}`
}

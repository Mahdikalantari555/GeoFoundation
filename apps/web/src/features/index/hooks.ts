import { useMutation } from '@tanstack/react-query'
import { opsApi } from '@/api/ops'

export function useBuildIndex() {
  return useMutation({ mutationFn: opsApi.buildIndex })
}

export function useRebuildIndex() {
  return useMutation({ mutationFn: opsApi.rebuildIndex })
}

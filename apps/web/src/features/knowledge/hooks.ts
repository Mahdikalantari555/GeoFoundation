import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { assetsApi, collectionsApi, entitiesApi, ingestApi, jobsApi, type EntityKind, type Job } from '@/api/knowledge'
import { useWorkspace } from '@/features/workspace/hooks'

export const knowledgeKeys = {
  collections: ['collections'] as const,
  assets: (collectionId?: string) => ['assets', collectionId ?? 'all'] as const,
  asset: (id: string) => ['asset', id] as const,
  entities: (kind?: EntityKind | null) => ['entities', kind ?? 'all'] as const,
  entityRelations: (id: string | null) => ['entity-relations', id ?? 'none'] as const,
  job: (id: string) => ['job', id] as const,
}

export function useCollections() {
  const { data: ws } = useWorkspace()
  return useQuery({
    queryKey: knowledgeKeys.collections,
    queryFn: collectionsApi.list,
    enabled: ws?.status === 'open',
  })
}

export function useCreateCollection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: collectionsApi.create,
    onSuccess: () => void qc.invalidateQueries({ queryKey: knowledgeKeys.collections }),
  })
}

export function useArchiveCollection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: collectionsApi.archive,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: knowledgeKeys.collections })
      void qc.invalidateQueries({ queryKey: ['assets'] })
    },
  })
}

export function useAssets(collectionId?: string) {
  const { data: ws } = useWorkspace()
  return useQuery({
    queryKey: knowledgeKeys.assets(collectionId),
    queryFn: () => assetsApi.list(collectionId),
    enabled: ws?.status === 'open',
  })
}

export function useAssetDetail(id: string | null) {
  return useQuery({
    queryKey: knowledgeKeys.asset(id ?? 'none'),
    queryFn: () => assetsApi.inspect(id!),
    enabled: !!id,
  })
}

export function useEntities(kind?: EntityKind | null) {
  const { data: ws } = useWorkspace()
  return useQuery({
    queryKey: knowledgeKeys.entities(kind),
    queryFn: () => entitiesApi.list(kind),
    enabled: ws?.status === 'open',
  })
}

export function useEntityRelations(id: string | null) {
  const { data: ws } = useWorkspace()
  return useQuery({
    queryKey: knowledgeKeys.entityRelations(id),
    queryFn: () => entitiesApi.relations(id!),
    enabled: ws?.status === 'open' && !!id,
  })
}

export function useIngest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      file,
      collectionId,
      indexAfter,
    }: {
      file: File
      collectionId: string
      indexAfter: boolean
    }) => ingestApi.file(file, collectionId, indexAfter),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['assets'] })
      void qc.invalidateQueries({ queryKey: ['stats'] })
    },
  })
}

/** Poll a job until terminal; returns terminal job. */
export function useJobPolling(jobId: string | null) {
  return useQuery({
    queryKey: knowledgeKeys.job(jobId ?? 'none'),
    queryFn: () => jobsApi.get(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'completed' || status === 'failed' || status === 'error' ? false : 500
    },
  })
}

export type { Job }

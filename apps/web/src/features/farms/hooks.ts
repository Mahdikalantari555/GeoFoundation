import { useQuery } from '@tanstack/react-query'
import { geoApi } from '@/api/geo'
import { useWorkspace } from '@/features/workspace/hooks'

export const farmKeys = {
  list: ['farms'] as const,
  detail: (id: string) => ['farm', id] as const,
  report: (id: string) => ['farm-report', id] as const,
  recommend: (id: string, topic: string) => ['farm-recommend', id, topic] as const,
}

export function useFarms() {
  const { data: ws } = useWorkspace()
  return useQuery({
    queryKey: farmKeys.list,
    queryFn: geoApi.listFarms,
    enabled: ws?.status === 'open',
  })
}

export function useFarmDetail(farmId: string | null) {
  return useQuery({
    queryKey: farmKeys.detail(farmId ?? 'none'),
    queryFn: () => geoApi.getFarm(farmId!),
    enabled: !!farmId,
  })
}

export function useFarmReport(farmId: string | null) {
  return useQuery({
    queryKey: farmKeys.report(farmId ?? 'none'),
    queryFn: () => geoApi.getReport(farmId!),
    enabled: !!farmId,
  })
}

export function useFarmRecommend(farmId: string | null, topic: string) {
  return useQuery({
    queryKey: farmKeys.recommend(farmId ?? 'none', topic),
    queryFn: () => geoApi.getRecommend(farmId!, topic),
    enabled: !!farmId,
  })
}

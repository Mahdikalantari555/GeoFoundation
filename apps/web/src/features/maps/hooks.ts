import { useQuery } from '@tanstack/react-query'
import { geoApi } from '@/api/geo'
import { useWorkspace } from '@/features/workspace/hooks'

export const mapsKeys = {
  list: (pattern: string) => ['maps', pattern] as const,
  geojson: (path: string) => ['maps-geojson', path] as const,
  zonal: (path: string) => ['maps-zonal', path] as const,
}

export function useMaps(pattern = 'runs/**/*') {
  const { data: ws } = useWorkspace()
  return useQuery({
    queryKey: mapsKeys.list(pattern),
    queryFn: () => geoApi.listMaps(pattern),
    enabled: ws?.status === 'open',
  })
}

export function useGeoJson(path: string | null) {
  return useQuery({
    queryKey: mapsKeys.geojson(path ?? 'none'),
    queryFn: () => geoApi.getGeoJson(path!),
    enabled: !!path,
  })
}

export function useZonal(path: string | null) {
  return useQuery({
    queryKey: mapsKeys.zonal(path ?? 'none'),
    queryFn: () => geoApi.getZonal(path!),
    enabled: !!path,
  })
}

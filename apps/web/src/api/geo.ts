import { request } from './client'

// ── Farms ──────────────────────────────────────────────────────────────────

export type FarmSummary = {
  farm_id: string
  properties: Record<string, unknown>
  bbox: [number, number, number, number] | null
  has_report: boolean
  report_dir: string | null
}

export type FarmsList = {
  farms: FarmSummary[]
  count: number
  source: string | null
  reports: { dir: string; name: string }[]
}

export type FarmDetail = {
  farm: {
    farm_id: string
    properties: Record<string, unknown>
    geometry: unknown
    bbox: [number, number, number, number] | null
  }
  report: {
    dir: string
    has_report_md: boolean
    has_stats_csv: boolean
    has_map_png: boolean
    map_png: string | null
    stats: Record<string, unknown>[]
    report_md: string | null
  } | null
}

export type FarmReport = {
  farm_id: string
  dir: string
  report_md: string
  stats: Record<string, unknown>[]
  map_png: string | null
  zonal_csvs: string[]
  files: { path: string; full: string; size: number }[]
  trend: {
    first: number | null
    last: number | null
    worst_date: string | null
    worst_mean: number | null
    worst_label: string | null
    count: number
  } | null
  sources: unknown[]
}

// ── Maps ───────────────────────────────────────────────────────────────────

export type MapsList = {
  artifacts: {
    path: string
    full_path: string
    name: string
    kind: string
    ext: string
    size: number
    modified: number
    dir: string
  }[]
  layers: {
    id: string
    path: string
    full_path: string
    name: string
    kind: string
    label: string
    size: number
    dir: string
    ext: string
  }[]
  count: number
  pattern: string
  legend: { class: string; count: number }[] | null
}

export type GeoJsonData = {
  path: string
  feature_count: number
  properties: string[]
  geojson: { type: string; features: unknown[]; _truncated?: boolean }
}

export type ZonalData = {
  path: string
  rows: Record<string, string>[]
  count: number
  fields: string[]
}

export const geoApi = {
  // farms
  listFarms: () => request<FarmsList>('/agent/farms'),
  getFarm: (farmId: string) => request<FarmDetail>(`/agent/farms/${encodeURIComponent(farmId)}`),
  getReport: (farmId: string) => request<FarmReport>(`/agent/farms/${encodeURIComponent(farmId)}/report`),
  getRecommend: (farmId: string, topic: string, reportDir?: string) => {
    const qs = new URLSearchParams({ topic })
    if (reportDir) qs.set('report_dir', reportDir)
    return request<{ value: { hits: { text: string; locator: unknown }[]; gaps: string[]; stress_state: Record<string, unknown> } } & Record<string, unknown>>(
      `/agent/farms/${encodeURIComponent(farmId)}/recommend?${qs.toString()}`,
    )
  },
  // maps
  listMaps: (pattern = 'runs/**/*') => request<MapsList>(`/agent/maps?pattern=${encodeURIComponent(pattern)}`),
  getGeoJson: (path: string) => request<GeoJsonData>(`/agent/maps/geojson?path=${encodeURIComponent(path)}`),
  getZonal: (path: string) => request<ZonalData>(`/agent/maps/zonal?path=${encodeURIComponent(path)}`),

  // helper for image / download urls (served via agent/files)
  fileDownloadUrl: (fullPath: string) => {
    return `/api/v1/agent/files/download?path=${encodeURIComponent(fullPath)}`
  },
}

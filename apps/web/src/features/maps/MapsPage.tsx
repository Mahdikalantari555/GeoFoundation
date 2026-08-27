import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Layers, Map as MapIcon, Eye, EyeOff, Image as ImageIcon, FileJson, Table as TableIcon, Search } from 'lucide-react'
import { useWorkspace } from '@/features/workspace/hooks'
import { useGeoJson, useMaps, useZonal } from './hooks'

function kindBadge(kind: string) {
  const map: Record<string, string> = {
    image: 'bg-sky-500/15 text-sky-700',
    vector: 'bg-emerald-500/15 text-emerald-700',
    raster: 'bg-amber-500/15 text-amber-700',
    table: 'bg-violet-500/15 text-violet-700',
    document: 'bg-zinc-500/15 text-zinc-600',
  }
  return map[kind] ?? 'border border-gf-border text-gf-muted'
}

export function MapsPage() {
  const { t } = useTranslation()
  const { data: ws } = useWorkspace()
  const [pattern, setPattern] = useState('runs/**/*')
  const [filter, setFilter] = useState('')
  const { data, isLoading, error, refetch } = useMaps(pattern)
  const [selected, setSelected] = useState<string | null>(null)
  const [opacity, setOpacity] = useState(85)
  const [showOverlay, setShowOverlay] = useState(true)

  const selectedLayer = useMemo(() => data?.layers.find((l) => l.path === selected) ?? null, [data, selected])
  const isImage = selectedLayer?.kind === 'image'
  const isVector = selectedLayer?.kind === 'vector' && (selectedLayer.ext === '.geojson' || selectedLayer.name.endsWith('.geojson'))
  const isZonal = selectedLayer?.kind === 'table' && selectedLayer.name.toLowerCase().includes('zonal')

  const geo = useGeoJson(isVector ? selected : null)
  const zonal = useZonal(isZonal || (selectedLayer?.kind === 'table') ? selected : null)

  // Find map.png among layers for choropleth
  const mapPng = data?.layers.find((l) => l.name === 'map.png') ?? null

  if (ws?.status !== 'open') {
    return (
      <div className="mx-auto max-w-5xl space-y-5">
        <h1 className="flex items-center gap-2 text-2xl font-semibold"><MapIcon className="size-6 text-gf-accent" />{t('maps.title', 'Maps')}</h1>
        <div className="rounded-lg border border-gf-border bg-gf-panel p-8 text-center">
          <p className="text-sm text-gf-muted">{t('maps.closed', 'Open a workspace to view map artifacts.')}</p>
        </div>
      </div>
    )
  }

  const filteredLayers = (data?.layers ?? []).filter((l) => {
    if (!filter) return true
    const q = filter.toLowerCase()
    return l.path.toLowerCase().includes(q) || l.kind.toLowerCase().includes(q) || l.name.toLowerCase().includes(q)
  })

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          <MapIcon className="size-6 text-gf-accent" />{t('maps.title', 'Maps')}
          {data && <span className="rounded-full border border-gf-border px-2 py-0.5 text-xs font-normal text-gf-muted">{data.count} {t('maps.artifacts', 'artifacts')}</span>}
        </h1>
        <button type="button" onClick={() => void refetch()} className="rounded-md border border-gf-border px-3 py-1.5 text-xs hover:bg-gf-accent-soft/40">{t('common.retry', 'Retry')}</button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1.5 rounded-md border border-gf-border bg-gf-panel px-2 py-1.5">
          <Search className="size-3.5 text-gf-muted" />
          <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder={t('maps.filterPlaceholder', 'Filter by name or kind…')} className="w-48 bg-transparent text-xs outline-none placeholder:text-gf-muted" />
        </div>
        <input value={pattern} onChange={(e) => setPattern(e.target.value)} placeholder="runs/**/*" className="w-40 rounded-md border border-gf-border bg-gf-panel px-2 py-1.5 font-mono text-xs outline-none focus:border-gf-accent" />
        <button type="button" onClick={() => void refetch()} className="rounded-md bg-gf-accent px-3 py-1.5 text-xs font-medium text-white">{t('maps.refresh', 'Refresh')}</button>
        {data?.legend && data.legend.length > 0 && (
          <span className="ms-2 text-xs text-gf-muted">{t('maps.legend', 'Legend')}: {data.legend.map((l) => `${l.class}×${l.count}`).join(' · ')}</span>
        )}
      </div>

      {isLoading && <p className="text-sm text-gf-muted">{t('common.loading', 'Loading…')}</p>}
      {error && <p className="rounded-md border border-gf-err/30 bg-gf-err/10 px-3 py-2 text-sm text-gf-err" role="alert">{error instanceof Error ? error.message : String(error)}</p>}

      {!isLoading && !data?.layers.length && (
        <div className="rounded-lg border border-dashed border-gf-border bg-gf-panel p-8 text-center">
          <Layers className="mx-auto mb-2 size-8 text-gf-muted" />
          <p className="text-sm font-medium">{t('maps.emptyTitle', 'No map artifacts yet')}</p>
          <p className="mx-auto mt-1 max-w-lg text-xs text-gf-muted">{t('maps.emptyBody', 'Run a farm report or GIS tool (e.g. geo_symbology) to generate map.png choropleths and GeoJSON overlays under runs/.')}</p>
        </div>
      )}

      {data && data.layers.length > 0 && (
        <div className="grid gap-5 lg:grid-cols-[360px_1fr]">
          {/* Layer list */}
          <div className="space-y-3">
            <div className="overflow-hidden rounded-lg border border-gf-border bg-gf-panel">
              <div className="flex items-center justify-between border-b border-gf-border px-3 py-2">
                <span className="flex items-center gap-1.5 text-xs font-medium"><Layers className="size-3.5" />{t('maps.layers', 'Layers')}</span>
                <label className="flex items-center gap-1.5 text-[11px] text-gf-muted">
                  {t('maps.opacity', 'Opacity')}
                  <input type="range" min={20} max={100} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} className="w-16 accent-gf-accent" />
                  <span className="w-7 text-end font-mono">{opacity}%</span>
                </label>
              </div>
              <div className="max-h-[520px] overflow-auto">
                {filteredLayers.map((l) => (
                  <button
                    key={l.id}
                    type="button"
                    onClick={() => setSelected(l.path)}
                    className={`flex w-full items-center gap-2 border-b border-gf-border/40 px-3 py-2 text-start hover:bg-gf-accent-soft/30 ${selected === l.path ? 'bg-gf-accent-soft/60' : ''}`}
                  >
                    <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${kindBadge(l.kind)}`}>{l.kind}</span>
                    <span className="min-w-0 flex-1 truncate font-mono text-[11px]">{l.label}</span>
                    <span className="shrink-0 text-[10px] text-gf-muted">{(l.size / 1024).toFixed(0)}k</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Legend */}
            {data.legend && (
              <div className="rounded-lg border border-gf-border bg-gf-panel p-3">
                <div className="mb-1 flex items-center gap-1.5 text-xs font-medium"><MapIcon className="size-3.5 text-gf-accent" />{t('maps.classLegend', 'Class legend')}</div>
                <div className="space-y-1">
                  {data.legend.map((row) => (
                    <div key={row.class} className="flex items-center justify-between gap-2 text-xs">
                      <span className="font-mono text-[11px]">class {row.class}</span>
                      <span className="text-gf-muted">{row.count} {t('maps.features', 'features')}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Viewer */}
          <div className="space-y-4">
            {/* Map.png choropleth */}
            {mapPng && (
              <div className="rounded-lg border border-gf-border bg-gf-panel p-3">
                <div className="mb-2 flex items-center gap-2 text-xs font-medium"><ImageIcon className="size-3.5" />{t('maps.choropleth', 'Choropleth')} — {mapPng.label}</div>
                <div className="relative overflow-hidden rounded-md border border-gf-border bg-gf-bg">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`/api/v1/agent/files/download?path=${encodeURIComponent(mapPng.full_path)}`}
                    alt="choropleth"
                    className="w-full object-contain"
                    style={{ opacity: opacity / 100 }}
                    onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')}
                  />
                  <button type="button" onClick={() => setShowOverlay((v) => !v)} className="absolute end-2 top-2 rounded-full bg-black/60 px-2 py-1 text-[11px] font-medium text-white backdrop-blur">
                    {showOverlay ? <span className="flex items-center gap-1"><Eye className="size-3" />{t('maps.hideOverlay', 'Hide overlay')}</span> : <span className="flex items-center gap-1"><EyeOff className="size-3" />{t('maps.showOverlay', 'Show overlay')}</span>}
                  </button>
                </div>
                <p className="mt-1 break-all font-mono text-[10px] text-gf-muted">{mapPng.full_path}</p>
              </div>
            )}

            {/* Selected layer viewer */}
            {selectedLayer && (
              <div className="rounded-lg border border-gf-border bg-gf-panel">
                <div className="flex items-center gap-2 border-b border-gf-border bg-gf-bg px-3 py-2">
                  {selectedLayer.kind === 'image' && <ImageIcon className="size-4 text-gf-accent" />}
                  {selectedLayer.kind === 'vector' && <FileJson className="size-4 text-gf-accent" />}
                  {selectedLayer.kind === 'table' && <TableIcon className="size-4 text-gf-accent" />}
                  <span className="truncate font-mono text-xs">{selectedLayer.label}</span>
                  <span className={`ms-auto rounded-full px-1.5 py-0.5 text-[10px] ${kindBadge(selectedLayer.kind)}`}>{selectedLayer.kind}</span>
                </div>

                <div className="p-3">
                  {/* Image preview */}
                  {isImage && (
                    <div className="rounded-md border border-gf-border bg-gf-bg p-2">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={`/api/v1/agent/files/download?path=${encodeURIComponent(selectedLayer.full_path)}`}
                        alt={selectedLayer.name}
                        className="max-h-80 w-full rounded-md object-contain"
                        style={{ opacity: opacity / 100 }}
                        onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')}
                      />
                    </div>
                  )}

                  {/* Vector GeoJSON */}
                  {isVector && (
                    <div className="space-y-2">
                      {geo.isLoading && <p className="text-xs text-gf-muted">{t('common.loading', 'Loading…')}</p>}
                      {geo.error && <p className="text-xs text-gf-err" role="alert">{geo.error instanceof Error ? geo.error.message : String(geo.error)}</p>}
                      {geo.data && (
                        <>
                          <p className="text-xs text-gf-muted">{geo.data.feature_count} {t('maps.features', 'features')} · {t('maps.properties', 'properties')}: {geo.data.properties.join(', ') || '—'}</p>
                          <div className="max-h-64 overflow-auto rounded-md border border-gf-border bg-gf-bg p-2">
                            <svg viewBox="0 0 200 200" className="h-48 w-full rounded-md bg-white">
                              {geo.data.geojson.features.slice(0, 80).map((f: unknown, idx: number) => {
                                const feat = f as { geometry?: { type: string; coordinates: unknown }; properties?: Record<string, unknown> }
                                const geom = feat.geometry
                                if (!geom) return null
                                // crude polygon render: assume Polygon exterior ring in lon/lat, map to 0..200
                                try {
                                  const coords = (geom.type === 'Polygon' ? (geom.coordinates as number[][][])[0] : (geom.coordinates as number[][][][])[0][0]) as number[][]
                                  if (!coords?.length) return null
                                  const xs = coords.map((c) => c[0]); const ys = coords.map((c) => c[1])
                                  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys)
                                  const pts = coords.map(([x, y]) => {
                                    const sx = ((x - minX) / (maxX - minX || 1)) * 180 + 10
                                    const sy = 190 - ((y - minY) / (maxY - minY || 1)) * 180
                                    return `${sx},${sy}`
                                  }).join(' ')
                                  const cls = String(feat.properties?.class ?? feat.properties?.Class ?? '')
                                  const fill = cls === '2' ? '#d73027' : cls === '1' ? '#fee08b' : cls === '0' ? '#1a9850' : '#93c5fd'
                                  return <polygon key={idx} points={pts} fill={fill} fillOpacity={0.55} stroke="#333" strokeWidth={0.5} />
                                } catch { return null }
                              })}
                            </svg>
                          </div>
                          <details className="rounded-md border border-gf-border">
                            <summary className="cursor-pointer px-2 py-1 text-xs font-medium">{t('maps.rawGeoJson', 'Raw GeoJSON (first 300 features)')}</summary>
                            <pre className="max-h-40 overflow-auto border-t border-gf-border bg-gf-bg p-2 text-[10px] leading-relaxed">{JSON.stringify(geo.data.geojson, null, 2).slice(0, 8000)}</pre>
                          </details>
                        </>
                      )}
                    </div>
                  )}

                  {/* Table / zonal */}
                  {(isZonal || selectedLayer.kind === 'table') && (
                    <div className="space-y-2">
                      {zonal.isLoading && <p className="text-xs text-gf-muted">{t('common.loading', 'Loading…')}</p>}
                      {zonal.error && <p className="text-xs text-gf-err" role="alert">{zonal.error instanceof Error ? zonal.error.message : String(zonal.error)}</p>}
                      {zonal.data && (
                        <>
                          <p className="text-xs text-gf-muted">{zonal.data.count} {t('maps.rows', 'rows')} · {t('maps.fields', 'fields')}: {zonal.data.fields.join(', ')}</p>
                          <div className="max-h-64 overflow-auto rounded-md border border-gf-border">
                            <table className="w-full text-xs">
                              <thead className="sticky top-0 bg-gf-bg text-gf-muted">
                                <tr>{zonal.data.fields.map((f) => <th key={f} className="px-2 py-1 text-start font-medium">{f}</th>)}</tr>
                              </thead>
                              <tbody>
                                {zonal.data.rows.map((r, i) => (
                                  <tr key={i} className="border-t border-gf-border/40">
                                    {zonal.data.fields.map((f) => <td key={f} className="px-2 py-1 font-mono text-[11px]">{String(r[f] ?? '—')}</td>)}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </>
                      )}
                    </div>
                  )}

                  {!isImage && !isVector && !(isZonal || selectedLayer.kind === 'table') && (
                    <p className="text-xs text-gf-muted">{t('maps.selectHint', 'Select an image, GeoJSON, or zonal CSV to preview.')}</p>
                  )}
                </div>
              </div>
            )}

            {!selected && <p className="rounded-lg border border-dashed border-gf-border bg-gf-panel p-6 text-center text-sm text-gf-muted">{t('maps.selectLayer', 'Select a layer to preview.')}</p>}
          </div>
        </div>
      )}
    </div>
  )
}

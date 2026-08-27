import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Tractor, AlertTriangle, MapPin, TrendingDown, Layers, FileText, Beaker } from 'lucide-react'
import { useWorkspace } from '@/features/workspace/hooks'
import { useFarms, useFarmDetail, useFarmReport, useFarmRecommend } from './hooks'

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return <span className="text-xs text-gf-muted">—</span>
  const w = 120, h = 32, pad = 2
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const pts = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - pad * 2)
    const y = h - pad - ((v - min) / range) * (h - pad * 2)
    return `${x},${y}`
  }).join(' ')
  const last = values[values.length - 1]
  const first = values[0]
  const trend = last < first ? 'down' : last > first ? 'up' : 'flat'
  const stroke = trend === 'down' ? '#d73027' : trend === 'up' ? '#1a9850' : '#6b7280'
  return (
    <svg width={w} height={h} className="overflow-visible" role="img" aria-label="sparkline">
      <polyline fill="none" stroke={stroke} strokeWidth={1.5} points={pts} />
      {values.map((_, i) => {
        const x = pad + (i / (values.length - 1)) * (w - pad * 2)
        const y = h - pad - ((values[i] - min) / range) * (h - pad * 2)
        return <circle key={i} cx={x} cy={y} r={1.5} fill={stroke} />
      })}
    </svg>
  )
}

export function FarmsPage() {
  const { t } = useTranslation()
  const { data: ws } = useWorkspace()
  const { data, isLoading, error, refetch } = useFarms()
  const [selected, setSelected] = useState<string | null>(null)
  const [topic, setTopic] = useState<'irrigation' | 'fertilization' | 'spraying'>('irrigation')

  const detail = useFarmDetail(selected)
  const report = useFarmReport(selected)
  const recommend = useFarmRecommend(selected, topic)

  if (ws?.status !== 'open') {
    return (
      <div className="mx-auto max-w-5xl space-y-5">
        <h1 className="flex items-center gap-2 text-2xl font-semibold"><Tractor className="size-6 text-gf-accent" />{t('farms.title', 'Farms')}</h1>
        <div className="rounded-lg border border-gf-border bg-gf-panel p-8 text-center">
          <p className="text-sm text-gf-muted">{t('farms.closed', 'Open a workspace to view farms.')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          <Tractor className="size-6 text-gf-accent" />{t('farms.title', 'Farms')}
        </h1>
        <button type="button" onClick={() => void refetch()} className="rounded-md border border-gf-border px-3 py-1.5 text-xs hover:bg-gf-accent-soft/40">
          {t('common.retry', 'Retry')}
        </button>
      </div>

      {isLoading && <p className="text-sm text-gf-muted">{t('common.loading', 'Loading…')}</p>}
      {error && (
        <p className="rounded-md border border-gf-err/30 bg-gf-err/10 px-3 py-2 text-sm text-gf-err" role="alert">
          {error instanceof Error ? error.message : String(error)}
        </p>
      )}

      {!isLoading && !data?.farms.length && (
        <div className="rounded-lg border border-dashed border-gf-border bg-gf-panel p-8 text-center">
          <Tractor className="mx-auto mb-2 size-8 text-gf-muted" />
          <p className="text-sm font-medium">{t('farms.emptyTitle', 'No farms registry found')}</p>
          <p className="mx-auto mt-1 max-w-lg text-xs text-gf-muted">
            {t('farms.emptyBody', 'Ingest a GeoJSON FeatureCollection where each feature has a farm_id property (e.g. farms.geojson) to populate the registry.')}
          </p>
          {data?.source && <p className="mt-2 font-mono text-[10px] text-gf-muted">{t('farms.source', 'Source')}: {data.source}</p>}
        </div>
      )}

      {data && data.farms.length > 0 && (
        <div className="grid gap-5 lg:grid-cols-[1.1fr_1.6fr]">
          {/* Registry table */}
          <div className="overflow-hidden rounded-lg border border-gf-border bg-gf-panel">
            <div className="border-b border-gf-border px-3 py-2 text-xs font-medium text-gf-muted">
              {t('farms.registry', 'Registry')} · {data.farms.length} {t('farms.farms', 'farms')}
              {data.source && <span className="ms-2 font-mono text-[10px]">({data.source.split('/').slice(-1)[0]})</span>}
            </div>
            <div className="max-h-[480px] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-gf-panel text-start text-xs text-gf-muted">
                  <tr className="border-b border-gf-border">
                    <th className="px-3 py-2 text-start font-medium">{t('farms.farmId', 'Farm')}</th>
                    <th className="px-3 py-2 text-start font-medium">{t('farms.crop', 'Crop')}</th>
                    <th className="px-3 py-2 text-start font-medium">{t('farms.report', 'Report')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.farms.map((f) => (
                    <tr
                      key={f.farm_id}
                      onClick={() => setSelected(f.farm_id)}
                      className={`cursor-pointer border-b border-gf-border/40 hover:bg-gf-accent-soft/40 ${selected === f.farm_id ? 'bg-gf-accent-soft/60' : ''}`}
                    >
                      <td className="px-3 py-2 font-medium">{f.farm_id}</td>
                      <td className="px-3 py-2 text-xs text-gf-muted">{String(f.properties.crop ?? f.properties.crop_type ?? '—')}</td>
                      <td className="px-3 py-2">
                        {f.has_report
                          ? <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] font-medium text-emerald-600">✓ {t('farms.hasReport', 'report')}</span>
                          : <span className="rounded-full border border-gf-border px-2 py-0.5 text-[11px] text-gf-muted">{t('farms.noReport', 'no report')}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Farm card */}
          <div className="space-y-4">
            {!selected && <p className="rounded-lg border border-dashed border-gf-border bg-gf-panel p-6 text-center text-sm text-gf-muted">{t('farms.selectHint', 'Select a farm to view its stress report.')}</p>}
            {selected && detail.isLoading && <p className="text-sm text-gf-muted">{t('common.loading', 'Loading…')}</p>}
            {selected && detail.data && (
              <div className="rounded-lg border border-gf-border bg-gf-panel p-4">
                <div className="mb-3 flex items-start justify-between gap-2">
                  <div>
                    <h2 className="flex items-center gap-1.5 text-base font-semibold"><MapPin className="size-4 text-gf-accent" />{selected}</h2>
                    <p className="text-xs text-gf-muted">
                      {detail.data.farm.bbox ? `bbox [${detail.data.farm.bbox.map((n) => n.toFixed(3)).join(', ')}]` : '—'}
                      {detail.data.farm.properties.crop ? ` · ${String(detail.data.farm.properties.crop)}` : ''}
                    </p>
                  </div>
                  <button type="button" onClick={() => setSelected(null)} className="rounded-md border border-gf-border px-2 py-1 text-xs">{t('common.close', 'Close')}</button>
                </div>

                {/* Report */}
                {!detail.data.report && (
                  <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3">
                    <div className="flex items-center gap-2 text-sm font-medium text-amber-700"><AlertTriangle className="size-4" />{t('farms.noReportTitle', 'No stress report yet')}</div>
                    <p className="mt-1 text-xs text-gf-muted">{t('farms.noReportBody', 'Run geo_farm_report for this farm (Tools → geo_farm_report) or generate rasters under rasters/*.tif to enable reporting.')}</p>
                  </div>
                )}
                {detail.data.report && (
                  <>
                    <div className="mb-3 flex flex-wrap gap-2 text-[11px]">
                      <span className={`rounded-full px-2 py-0.5 ${detail.data.report.has_report_md ? 'bg-emerald-500/15 text-emerald-700' : 'border border-gf-border text-gf-muted'}`}>report.md {detail.data.report.has_report_md ? '✓' : '—'}</span>
                      <span className={`rounded-full px-2 py-0.5 ${detail.data.report.has_stats_csv ? 'bg-emerald-500/15 text-emerald-700' : 'border border-gf-border text-gf-muted'}`}>stats.csv {detail.data.report.has_stats_csv ? '✓' : '—'}</span>
                      <span className={`rounded-full px-2 py-0.5 ${detail.data.report.has_map_png ? 'bg-emerald-500/15 text-emerald-700' : 'border border-gf-border text-gf-muted'}`}>map.png {detail.data.report.has_map_png ? '✓' : '—'}</span>
                    </div>

                    {report.data && (
                      <div className="space-y-4">
                        {/* Trend + sparkline */}
                        {report.data.trend && (
                          <div className="flex flex-wrap items-center gap-4 rounded-md border border-gf-border bg-gf-bg p-3">
                            <div className="space-y-1 text-xs">
                              <div className="flex items-center gap-1.5 font-medium"><TrendingDown className="size-3.5 text-gf-accent" />{t('farms.trend', 'Trend')}</div>
                              <div className="text-gf-muted">
                                {report.data.trend.count} {t('farms.dates', 'dates')} · {t('farms.worst', 'worst')}: {report.data.trend.worst_date} <span className="font-medium text-gf-text">({report.data.trend.worst_label})</span>
                              </div>
                              <div className="font-mono text-[11px]">{report.data.trend.first?.toFixed?.(3)} → {report.data.trend.last?.toFixed?.(3)}</div>
                            </div>
                            <div className="ms-auto">
                              <Sparkline values={report.data.stats.map((r: Record<string, unknown>) => {
                                const k = Object.keys(r).find((x) => x.startsWith('mean_')) ?? 'mean_ndvi'
                                const v = r[k]
                                return typeof v === 'number' ? v : typeof v === 'string' ? Number(v) : 0
                              })} />
                            </div>
                          </div>
                        )}

                        {/* Stats table */}
                        {report.data.stats.length > 0 && (
                          <div className="overflow-hidden rounded-md border border-gf-border">
                            <div className="border-b border-gf-border bg-gf-bg px-3 py-1.5 text-xs font-medium">{t('farms.statsTable', 'Per-date stress')}</div>
                            <div className="max-h-48 overflow-auto">
                              <table className="w-full text-xs">
                                <thead className="sticky top-0 bg-gf-bg text-gf-muted">
                                  <tr><th className="px-2 py-1 text-start">{t('farms.date', 'Date')}</th><th className="px-2 py-1 text-start">{t('farms.mean', 'Mean')}</th><th className="px-2 py-1 text-start">{t('farms.class', 'Class')}</th></tr>
                                </thead>
                                <tbody>
                                  {report.data.stats.map((r: Record<string, unknown>, i: number) => {
                                    const meanKey = Object.keys(r).find((k) => k.startsWith('mean_')) ?? 'mean'
                                    return (
                                      <tr key={i} className="border-t border-gf-border/40">
                                        <td className="px-2 py-1 font-mono text-[11px]">{String(r.date ?? '—')}</td>
                                        <td className="px-2 py-1">{r[meanKey] != null ? Number(r[meanKey]).toFixed(3) : '—'}</td>
                                        <td className="px-2 py-1"><span className="rounded-full border border-gf-border px-1.5 py-0.5 text-[10px]">{String(r.stress_label ?? r.stress_class ?? '—')}</span></td>
                                      </tr>
                                    )
                                  })}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}

                        {/* Map thumb */}
                        {report.data.map_png && (
                          <div className="rounded-md border border-gf-border p-2">
                            <div className="mb-1 flex items-center gap-1.5 text-xs font-medium"><Layers className="size-3.5" />{t('farms.mapThumb', 'Map — latest classified date')}</div>
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              src={`/api/v1/agent/files/download?path=${encodeURIComponent(report.data.map_png)}`}
                              alt="farm stress map"
                              className="max-h-64 w-full rounded-md border border-gf-border object-contain"
                              onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')}
                            />
                            <p className="mt-1 break-all font-mono text-[10px] text-gf-muted">{report.data.map_png}</p>
                          </div>
                        )}

                        {/* Sources */}
                        {report.data.report_md && (
                          <details className="rounded-md border border-gf-border">
                            <summary className="cursor-pointer list-none px-3 py-2 text-xs font-medium hover:bg-gf-accent-soft/30"><span className="flex items-center gap-1.5"><FileText className="size-3.5" />{t('farms.reportMd', 'report.md')}</span></summary>
                            <pre className="max-h-64 overflow-auto border-t border-gf-border bg-gf-bg p-3 text-[11px] leading-relaxed whitespace-pre-wrap">{report.data.report_md.slice(0, 6000)}</pre>
                          </details>
                        )}
                      </div>
                    )}
                  </>
                )}

                {/* Recommendation evidence pack */}
                <div className="mt-4 rounded-md border border-gf-border">
                  <div className="flex items-center gap-2 border-b border-gf-border bg-gf-bg px-3 py-2">
                    <Beaker className="size-4 text-gf-accent" />
                    <span className="text-sm font-medium">{t('farms.recommendation', 'Recommendation evidence pack')}</span>
                    <div className="ms-auto flex gap-1">
                      {(['irrigation', 'fertilization', 'spraying'] as const).map((k) => (
                        <button key={k} type="button" onClick={() => setTopic(k)} className={`rounded-full px-2 py-1 text-[11px] ${topic === k ? 'bg-gf-accent text-white' : 'border border-gf-border hover:bg-gf-accent-soft/30'}`}>{t(`farms.topic_${k}`, k)}</button>
                      ))}
                    </div>
                  </div>
                  <div className="p-3">
                    {recommend.isLoading && <p className="text-xs text-gf-muted">{t('common.loading', 'Loading…')}</p>}
                    {recommend.error && <p className="text-xs text-gf-err" role="alert">{recommend.error instanceof Error ? recommend.error.message : String(recommend.error)}</p>}
                    {recommend.data && (() => {
                      const v = (recommend.data as unknown as { value?: { gaps?: string[]; hits?: { text: string }[]; stress_state?: Record<string, unknown> } })?.value
                      const gaps: string[] = v?.gaps ?? []
                      const hits: { text: string }[] = v?.hits ?? []
                      const stress = v?.stress_state as Record<string, unknown> | undefined
                      const hasGaps = gaps.length > 0
                      return (
                        <div className="space-y-3">
                          {stress && (
                            <div className="rounded-md bg-gf-bg px-2.5 py-2 text-xs">
                              <span className="font-medium">{t('farms.stressState', 'Stress state')}</span>: <span className="rounded-full border border-gf-border px-1.5 py-0.5 text-[11px]">{String(stress.stress_label ?? stress.stress_class ?? '—')}</span>
                              {stress.date ? ` · ${String(stress.date)}` : ''}
                              {stress.mean != null ? ` · mean ${String(stress.mean)}` : ''}
                            </div>
                          )}
                          {hasGaps && (
                            <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2.5">
                              <div className="flex items-center gap-1.5 text-xs font-medium text-amber-700"><AlertTriangle className="size-3.5" />{t('farms.abstention', 'Abstention — data gaps')}</div>
                              <ul className="mt-1 list-disc ps-5 text-xs text-gf-muted">{gaps.map((g, i) => <li key={i}>{g}</li>)}</ul>
                              <p className="mt-1 text-[11px] text-gf-muted">{t('farms.gapsHint', 'Treat gaps as abstention triggers — ingest agronomy sources or run a fresh report before advising.')}</p>
                            </div>
                          )}
                          <div className="space-y-2">
                            <div className="text-xs font-medium">{t('farms.expertHits', 'Expert-rule hits')} ({hits.length})</div>
                            {hits.length === 0 && <p className="text-xs text-gf-muted">{t('farms.noHits', 'No expert rules found for this topic.')}</p>}
                            {hits.map((h, i) => (
                              <div key={i} className="rounded-md border border-gf-border bg-gf-bg p-2 text-xs">
                                <span className="me-1 font-mono text-[11px] font-semibold text-gf-accent">[S{i + 1}]</span>{String(h.text).slice(0, 400)}
                              </div>
                            ))}
                          </div>
                        </div>
                      )
                    })()}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

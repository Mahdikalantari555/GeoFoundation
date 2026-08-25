import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { X, FileText, Map, Code2, Table } from 'lucide-react'
import { useAssetDetail, useAssets, useCollections } from './hooks'
import type { Asset } from '@/api/knowledge'
import { cn } from '@/lib/utils'

const KIND_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  document: FileText,
  code: Code2,
  raster: Map,
  vector: Map,
  table: Table,
}

function kindIcon(kind: string) {
  return KIND_ICONS[kind] ?? FileText
}

export function AssetsPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const collectionFilter = params.get('collection') ?? ''
  const { data: collections } = useCollections()
  const { data: assets, isLoading } = useAssets(collectionFilter || undefined)
  const [selected, setSelected] = useState<string | null>(null)
  const { data: detail } = useAssetDetail(selected)

  useEffect(() => {
    return () => setSelected(null)
  }, [collectionFilter])

  const collectionName = (id: string) =>
    collections?.find((c) => c.id === id)?.name ?? id.slice(0, 8)

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{t('assets.title')}</h1>
        <select
          value={collectionFilter}
          onChange={(e) => {
            const v = e.target.value
            setParams(v ? { collection: v } : {}, { replace: true })
          }}
          className="rounded-md border border-gf-border bg-gf-panel px-2 py-1.5 text-sm"
          data-testid="asset-filter"
        >
          <option value="">{t('assets.allCollections')}</option>
          {(collections ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <p className="text-sm text-gf-muted">{t('common.loading')}</p>
      ) : !assets || assets.length === 0 ? (
        <p className="py-10 text-center text-sm text-gf-muted">{t('assets.empty')}</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gf-border bg-gf-panel">
          <table className="w-full text-sm" data-testid="assets-table">
            <thead>
              <tr className="border-b border-gf-border text-start text-xs text-gf-muted">
                <th className="px-4 py-2 text-start font-medium">{t('assets.kind')}</th>
                <th className="px-4 py-2 text-start font-medium">{t('assets.title')}</th>
                <th className="px-4 py-2 text-start font-medium">{t('assets.collection')}</th>
                <th className="px-4 py-2 text-start font-medium">{t('assets.created')}</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((a: Asset) => {
                const Icon = kindIcon(a.kind)
                return (
                  <tr
                    key={a.id}
                    onClick={() => setSelected(a.id)}
                    className={cn(
                      'cursor-pointer border-b border-gf-border/50 transition-colors last:border-0 hover:bg-gf-accent-soft/40',
                      selected === a.id && 'bg-gf-accent-soft/60'
                    )}
                  >
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-1.5">
                        <Icon className="size-4 text-gf-accent" />
                        {a.kind}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-medium">{a.title}</td>
                    <td className="px-4 py-2.5 text-gf-muted">{collectionName(a.collection_id)}</td>
                    <td className="px-4 py-2.5 text-gf-muted">
                      {a.created_at ? new Date(a.created_at).toLocaleDateString() : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {selected && detail && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={() => setSelected(null)}>
          <div
            className="h-full w-full max-w-lg overflow-y-auto border-s border-gf-border bg-gf-panel p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
            data-testid="asset-drawer"
          >
            <div className="mb-4 flex items-start justify-between gap-2">
              <div>
                <h2 className="text-lg font-semibold">{detail.asset.title}</h2>
                <p className="text-xs text-gf-muted">
                  {detail.asset.kind} · {detail.asset.id}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="rounded-md border border-gf-border p-1.5 text-gf-muted hover:text-gf-text"
              >
                <X className="size-4" />
              </button>
            </div>

            {detail.revision && (
              <section className="mb-4">
                <h3 className="mb-2 text-xs font-semibold text-gf-muted uppercase">
                  {t('assets.revision')}
                </h3>
                <dl className="space-y-1 text-xs">
                  <Row label={t('assets.hash')} value={String(detail.revision.hash ?? '—')} mono />
                  <Row label={t('assets.mime')} value={String(detail.revision.mime_type ?? '—')} />
                  <Row label={t('assets.size')} value={String(detail.revision.size_bytes ?? '—')} />
                </dl>
              </section>
            )}

            {detail.segments && detail.segments.length > 0 && (
              <section className="mb-4">
                <h3 className="mb-2 text-xs font-semibold text-gf-muted uppercase">
                  {t('assets.segments')} ({detail.segments.length})
                </h3>
                <div className="space-y-2">
                  {detail.segments.map((seg, i) => (
                    <div key={i} className="rounded-md border border-gf-border bg-gf-bg p-2.5 text-xs">
                      <p className="mb-1 font-mono text-[10px] text-gf-muted">
                        {JSON.stringify(seg.locator)}
                      </p>
                      <p className="line-clamp-4 whitespace-pre-wrap">
                        {String(seg.text ?? '')}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {detail.scenes && detail.scenes.length > 0 && (
              <section className="mb-4">
                <h3 className="mb-2 text-xs font-semibold text-gf-muted uppercase">
                  {t('assets.scenes')}
                </h3>
                <pre className="overflow-auto rounded-md bg-gf-bg p-3 text-[10px] leading-relaxed">
                  {JSON.stringify(detail.scenes, null, 2)}
                </pre>
              </section>
            )}

            {detail.layers && detail.layers.length > 0 && (
              <section className="mb-4">
                <h3 className="mb-2 text-xs font-semibold text-gf-muted uppercase">
                  {t('assets.layers')}
                </h3>
                <pre className="overflow-auto rounded-md bg-gf-bg p-3 text-[10px] leading-relaxed">
                  {JSON.stringify(detail.layers, null, 2)}
                </pre>
              </section>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex gap-2">
      <dt className="w-24 shrink-0 text-gf-muted">{label}</dt>
      <dd className={cn('min-w-0 break-all', mono && 'font-mono text-[10px]')}>{value}</dd>
    </div>
  )
}

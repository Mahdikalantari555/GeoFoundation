import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, SlidersHorizontal, ThumbsUp, ThumbsDown } from 'lucide-react'
import type { SearchHit, SearchMode } from '@/api/search'
import { ApiError } from '@/api/client'
import { useCollections } from '@/features/knowledge/hooks'
import { useWorkspace } from '@/features/workspace/hooks'
import { cn } from '@/lib/utils'
import { BBoxPicker, type BBox } from './BBoxPicker'
import { useHitFeedback, useSearch } from './hooks'

const MODES: SearchMode[] = ['sparse', 'dense', 'hybrid']

export function SearchPage() {
  const { t } = useTranslation()
  const { data: ws } = useWorkspace()
  const isOpen = ws?.status === 'open'

  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<SearchMode>('hybrid')
  const [topN, setTopN] = useState(5)
  const [showFilters, setShowFilters] = useState(false)

  const [selectedCollections, setSelectedCollections] = useState<string[]>([])
  const [sensorInput, setSensorInput] = useState('')
  const [spatialEnabled, setSpatialEnabled] = useState(false)
  const [bbox, setBbox] = useState<BBox | null>(null)
  const [temporalEnabled, setTemporalEnabled] = useState(false)
  const [temporalField, setTemporalField] = useState<'acquired_at' | 'observed_at' | 'published_at' | 'ingested_at'>('observed_at')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')

  const { result, run, isRunning, error } = useSearch()

  function execute() {
    if (!query.trim()) return
    run({
      query: query.trim(),
      mode,
      top_n: topN,
      collections: selectedCollections.length ? selectedCollections : undefined,
      sensor: sensorInput.trim()
        ? sensorInput.split(',').map((s) => s.trim()).filter(Boolean)
        : undefined,
      spatial: spatialEnabled && bbox ? { op: 'intersects', bbox } : undefined,
      temporal:
        temporalEnabled && (fromDate || toDate)
          ? { field: temporalField, from: fromDate || undefined, to: toDate || undefined }
          : undefined,
    })
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <h1 className="text-2xl font-semibold">{t('search.title')}</h1>

      <div
        className="space-y-3 rounded-lg border border-gf-border bg-gf-panel p-4"
        data-testid="search-bar"
      >
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && execute()}
            placeholder={t('search.queryPlaceholder')}
            disabled={!isOpen || isRunning}
            className="min-w-0 flex-1 rounded-md border border-gf-border bg-gf-bg px-3 py-2 text-sm outline-none focus:border-gf-accent disabled:opacity-50"
            data-testid="search-input"
          />
          <button
            type="button"
            onClick={execute}
            disabled={!isOpen || isRunning || !query.trim()}
            className="flex items-center gap-1.5 rounded-md bg-gf-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            data-testid="search-run"
          >
            <Search className="size-4" /> {t('search.run')}
          </button>
          <select
            value={topN}
            onChange={(e) => setTopN(Number(e.target.value))}
            aria-label={t('search.filters.topN')}
            className="rounded-md border border-gf-border bg-gf-bg px-2 py-2 text-sm"
          >
            {[5, 10, 20].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex rounded-md border border-gf-border p-0.5" role="tablist">
            {MODES.map((m) => (
              <button
                key={m}
                type="button"
                role="tab"
                aria-selected={mode === m}
                onClick={() => setMode(m)}
                className={cn(
                  'rounded px-3 py-1 text-xs font-medium capitalize transition-colors',
                  mode === m ? 'bg-gf-accent text-white' : 'text-gf-muted hover:text-gf-text'
                )}
                data-testid={`mode-${m}`}
              >
                {t(`search.modes.${m}`)}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setShowFilters((v) => !v)}
            className="flex items-center gap-1.5 rounded-md border border-gf-border px-3 py-1.5 text-xs text-gf-muted hover:text-gf-text"
            data-testid="filters-toggle"
          >
            <SlidersHorizontal className="size-3.5" />
            {showFilters ? t('search.filters.hide') : t('search.filters.show')}
          </button>
        </div>

        {showFilters && (
          <FilterPanel
            selectedCollections={selectedCollections}
            onToggleCollection={(id) =>
              setSelectedCollections((prev) =>
                prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
              )
            }
            sensorInput={sensorInput}
            onSensorChange={setSensorInput}
            spatialEnabled={spatialEnabled}
            onSpatialToggle={() => {
              setSpatialEnabled((v) => !v)
              setBbox(null)
            }}
            bbox={bbox}
            onBboxChange={setBbox}
            temporalEnabled={temporalEnabled}
            onTemporalToggle={() => {
              setTemporalEnabled((v) => !v)
              setFromDate('')
              setToDate('')
            }}
            temporalField={temporalField}
            onTemporalFieldChange={setTemporalField}
            fromDate={fromDate}
            onFromChange={setFromDate}
            toDate={toDate}
            onToChange={setToDate}
          />
        )}

        {error && (
          <p className="text-xs text-gf-err" role="alert" data-testid="search-error">
            {error instanceof ApiError ? error.message : String(error)}
          </p>
        )}
      </div>

      {!isOpen ? (
        <p className="py-10 text-center text-sm text-gf-muted">{t('search.closedWorkspace')}</p>
      ) : isRunning ? (
        <p className="text-sm text-gf-muted" data-testid="search-running">
          {t('common.loading')}
        </p>
      ) : result ? (
        result.total_hits === 0 ? (
          <p className="py-10 text-center text-sm text-gf-muted" data-testid="no-results">
            {t('search.noResults')}
          </p>
        ) : (
          <section className="space-y-3" data-testid="results">
            <p className="text-xs text-gf-muted">
              {t('search.resultsCount', { count: result.total_hits, ms: result.latency_ms ?? 0 })}
            </p>
            {result.hits.map((hit, i) => (
              <HitCard key={hit.id} hit={hit} rank={i + 1} query={result.query} />
            ))}
          </section>
        )
      ) : (
        <p className="py-10 text-center text-sm text-gf-muted">{t('search.runFirst')}</p>
      )}
    </div>
  )
}

interface FilterPanelProps {
  selectedCollections: string[]
  onToggleCollection: (id: string) => void
  sensorInput: string
  onSensorChange: (v: string) => void
  spatialEnabled: boolean
  onSpatialToggle: () => void
  bbox: BBox | null
  onBboxChange: (bbox: BBox | null) => void
  temporalEnabled: boolean
  onTemporalToggle: () => void
  temporalField: 'acquired_at' | 'observed_at' | 'published_at' | 'ingested_at'
  onTemporalFieldChange: (f: 'acquired_at' | 'observed_at' | 'published_at' | 'ingested_at') => void
  fromDate: string
  onFromChange: (v: string) => void
  toDate: string
  onToChange: (v: string) => void
}

function FilterPanel(p: FilterPanelProps) {
  const { t } = useTranslation()
  const { data: collections } = useCollections()
  const TEMPORAL_FIELDS = ['observed_at', 'acquired_at', 'published_at', 'ingested_at'] as const

  return (
    <div className="grid grid-cols-1 gap-4 border-t border-gf-border pt-3 sm:grid-cols-2" data-testid="filter-panel">
      <fieldset className="space-y-1.5">
        <legend className="text-xs font-medium text-gf-muted">{t('search.filters.collections')}</legend>
        {(collections ?? []).length === 0 && (
          <p className="text-xs text-gf-muted">{t('collections.empty')}</p>
        )}
        {(collections ?? []).map((c) => (
          <label key={c.id} className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={p.selectedCollections.includes(c.id)}
              onChange={() => p.onToggleCollection(c.id)}
              className="accent-gf-accent"
            />
            {c.name}
          </label>
        ))}
      </fieldset>

      <fieldset className="space-y-1.5">
        <legend className="text-xs font-medium text-gf-muted">{t('search.filters.sensor')}</legend>
        <input
          value={p.sensorInput}
          onChange={(e) => p.onSensorChange(e.target.value)}
          placeholder={t('search.filters.sensorHint')}
          className="w-full rounded-md border border-gf-border bg-gf-bg px-2 py-1.5 text-sm"
        />
      </fieldset>

      <fieldset className="space-y-2">
        <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-gf-muted">
          <input
            type="checkbox"
            checked={p.spatialEnabled}
            onChange={p.onSpatialToggle}
            className="accent-gf-accent"
            data-testid="spatial-toggle"
          />
          {t('search.filters.spatial')}
        </label>
        {p.spatialEnabled && <BBoxPicker value={p.bbox} onChange={p.onBboxChange} />}
      </fieldset>

      <fieldset className="space-y-2">
        <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-gf-muted">
          <input
            type="checkbox"
            checked={p.temporalEnabled}
            onChange={p.onTemporalToggle}
            className="accent-gf-accent"
            data-testid="temporal-toggle"
          />
          {t('search.filters.temporal')}
        </label>
        {p.temporalEnabled && (
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={p.temporalField}
              onChange={(e) => p.onTemporalFieldChange(e.target.value as typeof p.temporalField)}
              aria-label={t('search.filters.field')}
              className="rounded-md border border-gf-border bg-gf-bg px-2 py-1.5 text-xs"
            >
              {TEMPORAL_FIELDS.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
            <input
              type="date"
              value={p.fromDate}
              onChange={(e) => p.onFromChange(e.target.value)}
              aria-label={t('search.filters.from')}
              className="rounded-md border border-gf-border bg-gf-bg px-2 py-1.5 text-xs"
            />
            <span className="text-xs text-gf-muted">→</span>
            <input
              type="date"
              value={p.toDate}
              onChange={(e) => p.onToChange(e.target.value)}
              aria-label={t('search.filters.to')}
              className="rounded-md border border-gf-border bg-gf-bg px-2 py-1.5 text-xs"
            />
          </div>
        )}
      </fieldset>
    </div>
  )
}

function HitCard({ hit, rank, query }: { hit: SearchHit; rank: number; query: string }) {
  const { t } = useTranslation()
  const feedback = useHitFeedback()
  const direction = feedback.given[hit.id]
  const title =
    (hit.metadata['title'] as string | undefined) ??
    (hit.metadata['asset_id'] as string | undefined) ??
    hit.locator['asset_id'] as string | undefined

  return (
    <article className="rounded-lg border border-gf-border bg-gf-panel p-4" data-testid="hit-card">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <span className="text-xs text-gf-muted">#{rank}</span>
          {title && <h3 className="truncate text-sm font-medium">{title}</h3>}
        </div>
        <div className="flex shrink-0 items-center gap-1.5 text-[11px]">
          <ScoreChip label={t('search.hits.score')} value={hit.score} strong />
          {hit.sparse_score != null && (
            <ScoreChip label={t('search.hits.sparse')} value={hit.sparse_score} />
          )}
          {hit.dense_score != null && (
            <ScoreChip label={t('search.hits.dense')} value={hit.dense_score} />
          )}
        </div>
      </div>

      <p className="line-clamp-4 whitespace-pre-wrap text-sm text-gf-text/90">{hit.text}</p>

      <div className="mt-2 flex items-center justify-between gap-2">
        <code className="truncate text-[11px] text-gf-muted">{JSON.stringify(hit.locator)}</code>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            title={t('search.feedback.up')}
            aria-label={t('search.feedback.up')}
            disabled={direction === 'up' || feedback.isPending}
            onClick={() => feedback.record({ segmentId: hit.id, direction: 'up', query })}
            className={cn(
              'rounded border border-gf-border p-1 transition-colors hover:border-gf-ok hover:text-gf-ok',
              direction === 'up' && 'border-gf-ok text-gf-ok'
            )}
          >
            <ThumbsUp className="size-3.5" />
          </button>
          <button
            type="button"
            title={t('search.feedback.down')}
            aria-label={t('search.feedback.down')}
            disabled={direction === 'down' || feedback.isPending}
            onClick={() => feedback.record({ segmentId: hit.id, direction: 'down', query })}
            className={cn(
              'rounded border border-gf-border p-1 transition-colors hover:border-gf-err hover:text-gf-err',
              direction === 'down' && 'border-gf-err text-gf-err'
            )}
          >
            <ThumbsDown className="size-3.5" />
          </button>
        </div>
      </div>
    </article>
  )
}

function ScoreChip({ label, value, strong }: { label: string; value: number; strong?: boolean }) {
  return (
    <span
      className={cn(
        'rounded-full px-2 py-0.5 tabular-nums',
        strong ? 'bg-gf-accent-soft text-gf-accent' : 'border border-gf-border text-gf-muted'
      )}
    >
      {label} {value.toFixed(3)}
    </span>
  )
}

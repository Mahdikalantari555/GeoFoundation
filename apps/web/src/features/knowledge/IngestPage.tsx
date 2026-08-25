import { useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Upload, FileWarning, CheckCircle2, Loader2, Copy } from 'lucide-react'
import { useCollections, useIngest, useJobPolling } from './hooks'
import { ApiError } from '@/api/client'
import { cn } from '@/lib/utils'

const ACCEPT = '.txt,.md,.markdown,.csv,.pdf,.py,.js,.ipynb,.geojson,.gpkg,.tif,.tiff'

type IngestState =
  | { phase: 'idle' }
  | { phase: 'uploading'; filename: string }
  | { phase: 'error'; filename: string; message: string }

export function IngestPage() {
  const { t } = useTranslation()
  const { data: collections } = useCollections()
  const ingest = useIngest()
  const [collectionId, setCollectionId] = useState('')
  const [indexAfter, setIndexAfter] = useState(true)
  const [dragOver, setDragOver] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [state, setState] = useState<IngestState>({ phase: 'idle' })
  const inputRef = useRef<HTMLInputElement>(null)

  // Effective selection: explicit choice, else first collection (derived, no effect).
  const effectiveCollectionId = collectionId || collections?.[0]?.id || ''

  const { data: job } = useJobPolling(jobId)

  // Derived terminal outcome — no state sync needed.
  const outcome = useMemo(() => {
    if (!job || job.status === 'pending' || job.status === 'running') return null
    if (job.status === 'failed') {
      return { kind: 'error' as const, message: job.error ?? t('ingest.failed') }
    }
    const r = (job.result ?? {}) as Record<string, unknown>
    return {
      kind: 'done' as const,
      skipped: r.skipped === true,
      segmentCount: typeof r.segment_count === 'number' ? r.segment_count : undefined,
      reason: typeof r.reason === 'string' ? r.reason : undefined,
    }
  }, [job, t])

  function startUpload(file: File) {
    if (!effectiveCollectionId) {
      setState({ phase: 'error', filename: file.name, message: t('ingest.noCollection') })
      return
    }
    setState({ phase: 'uploading', filename: file.name })
    ingest.mutate(
      { file, collectionId: effectiveCollectionId, indexAfter },
      {
        onSuccess: (resp) => setJobId(resp.job_id),
        onError: (e) =>
          setState({
            phase: 'error',
            filename: file.name,
            message: e instanceof ApiError ? e.message : String(e),
          }),
      }
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <h1 className="text-2xl font-semibold">{t('ingest.title')}</h1>

      <div className="space-y-3 rounded-lg border border-gf-border bg-gf-panel p-4">
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <span className="text-gf-muted">{t('ingest.collection')}</span>
            <select
              value={effectiveCollectionId}
              onChange={(e) => setCollectionId(e.target.value)}
              className="min-w-40 rounded-md border border-gf-border bg-gf-bg px-2 py-1.5 text-sm"
              data-testid="ingest-collection"
            >
              {(collections ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={indexAfter}
              onChange={(e) => setIndexAfter(e.target.checked)}
            />
            {t('ingest.indexAfter')}
          </label>
        </div>
        <p className="text-xs text-gf-muted">{t('ingest.formats')}</p>
      </div>

      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          const file = e.dataTransfer.files[0]
          if (file) startUpload(file)
        }}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-10 transition-colors',
          dragOver ? 'border-gf-accent bg-gf-accent-soft/40' : 'border-gf-border bg-gf-panel'
        )}
        data-testid="ingest-dropzone"
      >
        <Upload className="size-8 text-gf-accent" />
        <p className="text-sm font-medium">{t('ingest.dropTitle')}</p>
        <p className="text-xs text-gf-muted">{t('ingest.dropHint')}</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) startUpload(file)
            e.target.value = ''
          }}
        />
      </div>

      {state.phase === 'uploading' && (
        <div className="flex items-center gap-2 rounded-lg border border-gf-border bg-gf-panel p-4 text-sm">
          <Loader2 className="size-4 animate-spin text-gf-accent" />
          {t('ingest.processing', { name: state.filename })}
        </div>
      )}

      {outcome?.kind === 'done' && (
        <div
          className={cn(
            'flex items-start gap-2 rounded-lg border p-4 text-sm',
            outcome.skipped
              ? 'border-gf-warn/50 bg-gf-warn/10'
              : 'border-gf-ok/50 bg-gf-ok/10'
          )}
          data-testid="ingest-result"
        >
          {outcome.skipped ? (
            <Copy className="mt-0.5 size-4 shrink-0 text-gf-warn" />
          ) : (
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-gf-ok" />
          )}
          <div>
            {outcome.skipped ? (
              <>
                <p className="font-medium text-gf-warn">
                  {t('ingest.duplicateTitle', { name: state.phase === 'idle' ? '' : state.filename })}
                </p>
                <p className="text-xs text-gf-muted">
                  {t('ingest.duplicateBody')}
                  {outcome.reason ? ` (${outcome.reason})` : ''}
                </p>
              </>
            ) : (
              <p className="font-medium text-gf-ok">
                {t('ingest.successTitle', {
                  name: state.phase === 'idle' ? '' : state.filename,
                  count: outcome.segmentCount ?? 0,
                })}
              </p>
            )}
          </div>
        </div>
      )}

      {outcome?.kind === 'error' && (
        <div className="flex items-start gap-2 rounded-lg border border-gf-err/50 bg-gf-err/10 p-4 text-sm" role="alert">
          <FileWarning className="mt-0.5 size-4 shrink-0 text-gf-err" />
          <div>
            <p className="font-medium text-gf-err">
              {state.phase === 'idle' ? '' : state.filename}
            </p>
            <p className="text-xs">{outcome.message}</p>
          </div>
        </div>
      )}

    </div>
  )
}

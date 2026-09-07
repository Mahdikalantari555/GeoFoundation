import { useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Upload, FileWarning, CheckCircle2, Loader2, Copy, AlertCircle } from 'lucide-react'
import { useCollections, useIngest, useJobPolling } from './hooks'
import { useWorkspace } from '@/features/workspace/hooks'
import { ApiError } from '@/api/client'
import { cn } from '@/lib/utils'

const ACCEPT = '.txt,.md,.markdown,.csv,.pdf,.py,.js,.ipynb,.geojson,.gpkg,.tif,.tiff'

type IngestState =
  | { phase: 'idle' }
  | { phase: 'uploading'; filename: string }
  | { phase: 'error'; filename: string; message: string; detail?: unknown; code?: string }

export function IngestPage() {
  const { t } = useTranslation()
  const { data: collections } = useCollections()
  const { data: ws } = useWorkspace()
  const isOpen = ws?.status === 'open'
  const ingest = useIngest()
  const [collectionId, setCollectionId] = useState('')
  const [indexAfter, setIndexAfter] = useState(true)
  const [dragOver, setDragOver] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [state, setState] = useState<IngestState>({ phase: 'idle' })
  const inputRef = useRef<HTMLInputElement>(null)

  const effectiveCollectionId = collectionId || collections?.[0]?.id || ''

  const { data: job, refetch: refetchJob } = useJobPolling(jobId)

  const outcome = useMemo(() => {
    if (!job || job.status === 'pending' || job.status === 'running') return null
    if (job.status === 'failed' || job.status === 'error') {
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

  const isSubmitting = ingest.isPending || job?.status === 'pending' || job?.status === 'running'

  function startUpload(file: File) {
    if (!isOpen) {
      setState({ phase: 'error', filename: file.name, message: 'No workspace open — open a workspace first.' })
      return
    }
    if (!effectiveCollectionId) {
      setState({ phase: 'error', filename: file.name, message: t('ingest.noCollection') })
      return
    }
    setState({ phase: 'uploading', filename: file.name })
    ingest.mutate(
      { file, collectionId: effectiveCollectionId, indexAfter },
      {
        onSuccess: (resp) => setJobId(resp.job_id),
        onError: (e) => {
          const isApi = e instanceof ApiError
          const detail = isApi ? e.detail : undefined
          const code = isApi ? e.code : undefined
          // Surface accepted list for unsupported_format, size for payload_too_large
          let msg = isApi ? e.message : String(e)
          if (code === 'unsupported_format' && detail && typeof detail === 'object' && 'accepted' in (detail as Record<string, unknown>)) {
            const acc = (detail as Record<string, unknown>).accepted
            msg += acc ? ` — accepted: ${Array.isArray(acc) ? acc.join(', ') : String(acc)}` : ''
          }
          if (code === 'payload_too_large' && detail && typeof detail === 'object') {
            const d = detail as Record<string, unknown>
            msg += ` — size ${d.size_bytes ?? '?'} / limit ${d.limit_bytes ?? '?'}`
          }
          setState({ phase: 'error', filename: file.name, message: msg, detail, code })
        },
      }
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <h1 className="text-2xl font-semibold">{t('ingest.title')}</h1>

      {!isOpen && (
        <div className="flex items-center gap-2 rounded-lg border border-gf-warn/50 bg-gf-warn/10 p-3 text-sm" role="alert">
          <AlertCircle className="size-4 text-gf-warn" />
          <span>{t('search.closedWorkspace')}</span>
        </div>
      )}

      <div className="space-y-3 rounded-lg border border-gf-border bg-gf-panel p-4">
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <span className="text-gf-muted">{t('ingest.collection')}</span>
            <select
              value={effectiveCollectionId}
              onChange={(e) => setCollectionId(e.target.value)}
              disabled={!isOpen}
              className="min-w-40 rounded-md border border-gf-border bg-gf-bg px-2 py-1.5 text-sm disabled:opacity-50"
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
            <input type="checkbox" checked={indexAfter} onChange={(e) => setIndexAfter(e.target.checked)} disabled={!isOpen} />
            {t('ingest.indexAfter')}
          </label>
        </div>
        <p className="text-xs text-gf-muted">{t('ingest.formats')}</p>
        {!effectiveCollectionId && isOpen && (
          <p className="text-xs text-gf-err">Select a collection</p>
        )}
      </div>

      <div
        role="button"
        tabIndex={0}
        onClick={() => isOpen && inputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && isOpen && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          if (isOpen) setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          if (!isOpen) return
          const file = e.dataTransfer.files[0]
          if (file) startUpload(file)
        }}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-10 transition-colors',
          !isOpen && 'cursor-not-allowed opacity-50',
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
          disabled={!isOpen}
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) startUpload(file)
            e.target.value = ''
          }}
        />
      </div>

      {isSubmitting && (
        <div className="flex items-center gap-2 rounded-lg border border-gf-border bg-gf-panel p-4 text-sm">
          <Loader2 className="size-4 animate-spin text-gf-accent" />
          {state.phase === 'uploading' ? t('ingest.processing', { name: state.filename }) : `Job ${job?.status ?? 'queued'}…`}
          {job && <span className="ms-auto font-mono text-xs">{job.status} · {Math.round(job.progress * 100)}%</span>}
        </div>
      )}

      {state.phase === 'error' && !outcome && (
        <div className="flex items-start gap-2 rounded-lg border border-gf-err/50 bg-gf-err/10 p-4 text-sm" role="alert">
          <FileWarning className="mt-0.5 size-4 shrink-0 text-gf-err" />
          <div className="flex-1">
            <p className="font-medium text-gf-err">{state.filename} — {state.code ?? 'error'}</p>
            <p className="text-xs">{state.message}</p>
            {state.code === 'unsupported_format' && Boolean(state.detail) && (
              <p className="mt-1 text-xs text-gf-muted">Accepted: {String(((state.detail as unknown as Record<string, unknown>).accepted as unknown as string[] | undefined)?.join(', ') ?? '')}</p>
            )}
          </div>
          <button type="button" onClick={() => setState({ phase: 'idle' })} className="rounded border border-gf-border px-2 py-1 text-xs">Dismiss</button>
        </div>
      )}

      {outcome?.kind === 'done' && (
        <div
          className={cn(
            'flex items-start gap-2 rounded-lg border p-4 text-sm',
            outcome.skipped ? 'border-gf-warn/50 bg-gf-warn/10' : 'border-gf-ok/50 bg-gf-ok/10'
          )}
          data-testid="ingest-result"
        >
          {outcome.skipped ? <Copy className="mt-0.5 size-4 shrink-0 text-gf-warn" /> : <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-gf-ok" />}
          <div>
            {outcome.skipped ? (
              <>
                <p className="font-medium text-gf-warn">{t('ingest.duplicateTitle', { name: state.phase === 'idle' ? '' : (state as { filename?: string }).filename ?? '' })}</p>
                <p className="text-xs text-gf-muted">{t('ingest.duplicateBody')}{outcome.reason ? ` (${outcome.reason})` : ''}</p>
              </>
            ) : (
              <p className="font-medium text-gf-ok">{t('ingest.successTitle', { name: state.phase === 'idle' ? '' : (state as { filename?: string }).filename ?? '', count: outcome.segmentCount ?? 0 })}</p>
            )}
          </div>
        </div>
      )}

      {outcome?.kind === 'error' && (
        <div className="flex items-start gap-2 rounded-lg border border-gf-err/50 bg-gf-err/10 p-4 text-sm" role="alert">
          <FileWarning className="mt-0.5 size-4 shrink-0 text-gf-err" />
          <div className="flex-1">
            <p className="font-medium text-gf-err">{state.phase === 'idle' ? '' : (state as { filename?: string }).filename ?? ''}</p>
            <p className="text-xs">{outcome.message}</p>
          </div>
          <button type="button" onClick={() => refetchJob()} className="rounded border border-gf-border px-2 py-1 text-xs">Retry</button>
        </div>
      )}
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Download, FolderOpen, Save } from 'lucide-react'
import { ApiError } from '@/api/client'
import type { UpdateSettingsRequest, WorkspaceSettings } from '@/api/workspace'
import { useUpdateSettings, useWorkspace } from './hooks'
import { useModels, useDownloadModel, formatBytes } from './modelHooks'

const DEFAULT_KEY_ENV = 'GEOMEMORY_LLM_API_KEY'
const EMBEDDING_BACKENDS = ['hashing', 'sentence-transformers', 'onnx', 'llama-cpp'] as const

export function SettingsPage() {
  const { t } = useTranslation()
  const { data: ws } = useWorkspace()
  const update = useUpdateSettings()
  const settings = ws?.settings ?? null

  const [form, setForm] = useState<WorkspaceSettings | null>(null)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const modelDirRef = useRef<HTMLInputElement>(null)
  const embedDirRef = useRef<HTMLInputElement>(null)
  const visionDirRef = useRef<HTMLInputElement>(null)

  function pickDir(
    ref: React.RefObject<HTMLInputElement | null>,
    key: 'model_path' | 'embedding_path' | 'vision_path',
  ) {
    const input = ref.current
    if (!input) return
    input.onchange = (e) => {
      const files = (e.target as HTMLInputElement).files
      if (files && files.length > 0) {
        const f = files[0] as File & { webkitRelativePath?: string }
        const dir = (f.webkitRelativePath ?? '').split('/')[0] || f.name
        const base = (form?.[key] ?? '').trim()
        set(key, base && !base.endsWith(dir) ? `${base.replace(/\/$/, '')}/${dir}` : dir)
      }
      ;(e.target as HTMLInputElement).value = ''
    }
    input.click()
  }

  useEffect(() => {
    if (settings) setForm(settings)
  }, [settings])

  if (!settings || !form) {
    return (
      <div className="mx-auto max-w-3xl" data-testid="settings-page">
        <h1 className="text-2xl font-semibold">{t('settings.title')}</h1>
        <p className="mt-4 text-sm text-gf-muted">{t('closedWorkspace')}</p>
      </div>
    )
  }

  function set<K extends keyof WorkspaceSettings>(key: K, value: WorkspaceSettings[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev))
  }

  function submit() {
    if (!form) return
    setError(null)
    setSaved(false)
    const body: UpdateSettingsRequest = {
      name: form.name,
      language: form.language,
      offline: form.offline,
      model_path: form.model_path,
      embedding_path: form.embedding_path,
      vision_path: form.vision_path,
      batch_size: form.batch_size,
      thread_count: form.thread_count,
      llm_provider: form.llm_provider,
      llm_api_base_url: form.llm_api_base_url,
      llm_api_key_env: form.llm_api_key_env || DEFAULT_KEY_ENV,
      llm_model_id: form.llm_model_id,
      llm_context_window: form.llm_context_window,
      embedding_backend: form.embedding_backend,
      st_model_name: form.st_model_name,
      onnx_model_name: form.onnx_model_name,
      vector_backend: form.vector_backend,
      pdf_parser: form.pdf_parser,
    }
    update.mutate(body, {
      onSuccess: () => setSaved(true),
      onError: (e) => setError(e instanceof ApiError ? e.message : String(e)),
    })
  }

  const inputCls =
    'w-full rounded-md border border-gf-border bg-gf-bg px-3 py-2 text-sm outline-none focus:border-gf-accent'

  return (
    <div className="mx-auto max-w-3xl space-y-6" data-testid="settings-page">
      <h1 className="text-2xl font-semibold">{t('settings.title')}</h1>

      {/* ── General ─────────────────────────────────────────────── */}
      <section className="space-y-3 rounded-lg border border-gf-border bg-gf-panel p-4">
        <h2 className="text-sm font-medium text-gf-muted">{t('settings.general')}</h2>
        <label className="block text-sm">
          {t('settings.name')}
          <input className={inputCls} value={form.name} onChange={(e) => set('name', e.target.value)} />
        </label>
        <label className="block text-sm">
          {t('settings.language')}
          <input
            className={inputCls}
            value={form.language ?? ''}
            onChange={(e) => set('language', e.target.value || null)}
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.offline}
            onChange={(e) => set('offline', e.target.checked)}
          />
          {t('settings.offline')}
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            {t('settings.batchSize')}
            <input
              type="number"
              className={inputCls}
              value={form.batch_size}
              onChange={(e) => set('batch_size', Number(e.target.value))}
            />
          </label>
          <label className="block text-sm">
            {t('settings.threadCount')}
            <input
              type="number"
              className={inputCls}
              value={form.thread_count}
              onChange={(e) => set('thread_count', Number(e.target.value))}
            />
          </label>
        </div>
      </section>

      {/* ── Model Paths ─────────────────────────────────────────── */}
      <section className="space-y-3 rounded-lg border border-gf-border bg-gf-panel p-4">
        <h2 className="text-sm font-medium text-gf-muted">{t('settings.models')}</h2>
        <label className="flex items-center gap-2 text-sm">
          {t('settings.modelPath')}
          <input
            className={inputCls}
            value={form.model_path ?? ''}
            onChange={(e) => set('model_path', e.target.value || null)}
          />
          <button
            type="button"
            onClick={() => pickDir(modelDirRef, 'model_path')}
            className="shrink-0 rounded-md border border-gf-border px-2 py-1 text-xs"
            title={t('workspace.browse')}
          >
            <FolderOpen className="size-3.5" />
          </button>
        </label>
        <label className="flex items-center gap-2 text-sm">
          {t('settings.embeddingPath')}
          <input
            className={inputCls}
            value={form.embedding_path ?? ''}
            onChange={(e) => set('embedding_path', e.target.value || null)}
          />
          <button
            type="button"
            onClick={() => pickDir(embedDirRef, 'embedding_path')}
            className="shrink-0 rounded-md border border-gf-border px-2 py-1 text-xs"
            title={t('workspace.browse')}
          >
            <FolderOpen className="size-3.5" />
          </button>
        </label>
        <label className="flex items-center gap-2 text-sm">
          {t('settings.visionPath')}
          <input
            className={inputCls}
            value={form.vision_path ?? ''}
            onChange={(e) => set('vision_path', e.target.value || null)}
          />
          <button
            type="button"
            onClick={() => pickDir(visionDirRef, 'vision_path')}
            className="shrink-0 rounded-md border border-gf-border px-2 py-1 text-xs"
            title={t('workspace.browse')}
          >
            <FolderOpen className="size-3.5" />
          </button>
        </label>
        <input ref={modelDirRef} type="file" className="hidden" {...{ webkitdirectory: '' }} />
        <input ref={embedDirRef} type="file" className="hidden" {...{ webkitdirectory: '' }} />
        <input ref={visionDirRef} type="file" className="hidden" {...{ webkitdirectory: '' }} />
      </section>

      {/* ── Embedding Models (NEW) ──────────────────────────────── */}
      <EmbeddingModelsSection
        form={form}
        set={set}
        inputCls={inputCls}
        offline={form.offline}
      />

      {/* ── LLM Compute ─────────────────────────────────────────── */}
      <section className="space-y-3 rounded-lg border border-gf-border bg-gf-panel p-4">
        <h2 className="text-sm font-medium text-gf-muted">{t('settings.llm')}</h2>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            {t('settings.llmProvider')}
            <input
              className={inputCls}
              value={form.llm_provider ?? ''}
              onChange={(e) => set('llm_provider', e.target.value || null)}
            />
          </label>
          <label className="block text-sm">
            {t('settings.llmModelId')}
            <input
              className={inputCls}
              value={form.llm_model_id}
              onChange={(e) => set('llm_model_id', e.target.value)}
            />
          </label>
          <label className="block text-sm">
            {t('settings.llmBaseUrl')}
            <input
              className={inputCls}
              value={form.llm_api_base_url ?? ''}
              onChange={(e) => set('llm_api_base_url', e.target.value || null)}
            />
          </label>
          <label className="block text-sm">
            {t('settings.llmContextWindow')}
            <input
              type="number"
              className={inputCls}
              value={form.llm_context_window}
              onChange={(e) => set('llm_context_window', Number(e.target.value))}
            />
          </label>
        </div>
        <label className="block text-sm">
          {t('settings.llmKeyEnv')}
          <input
            className={inputCls}
            value={form.llm_api_key_env}
            onChange={(e) => set('llm_api_key_env', e.target.value)}
          />
        </label>
        <p className="text-xs text-gf-err">{t('settings.llmKeyHint')}</p>
      </section>

      {/* ── Save ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={submit}
          disabled={update.isPending}
          className="flex items-center gap-1.5 rounded-md bg-gf-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          <Save className="size-4" /> {t('common.save')}
        </button>
        {saved && <span className="text-xs text-gf-accent">{t('settings.saved')}</span>}
        {error && (
          <span className="text-xs text-gf-err" role="alert">
            {error}
          </span>
        )}
      </div>
    </div>
  )
}

/* ── Embedding Models sub-section ──────────────────────────────────────── */

function EmbeddingModelsSection({
  form,
  set,
  inputCls,
  offline,
}: {
  form: WorkspaceSettings
  set: <K extends keyof WorkspaceSettings>(key: K, value: WorkspaceSettings[K]) => void
  inputCls: string
  offline: boolean
}) {
  const { t } = useTranslation()
  const { data: models } = useModels()
  const download = useDownloadModel()

  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  const backend = form.embedding_backend
  const isDense = backend === 'sentence-transformers' || backend === 'onnx'
  const activeTag = backend === 'onnx' ? 'onnx' : 'st'

  const filteredModels = (models ?? []).filter(
    (m) => m.backend === activeTag || !isDense,
  )

  const activeModelName = backend === 'onnx' ? form.onnx_model_name : form.st_model_name
  const activeSpaceId = isDense
    ? `text.${activeTag}.${(activeModelName ?? '').replace(/[/.]/g, '-').replace(/-+$/, '')}.v1`
    : null

  function handleDownload(modelName: string, modelBackend: 'st' | 'onnx') {
    setDownloadingId(modelName)
    download.mutate(
      { model_name: modelName, backend: modelBackend },
      {
        onSettled: () => setDownloadingId(null),
      },
    )
  }

  return (
    <section className="space-y-3 rounded-lg border border-gf-border bg-gf-panel p-4">
      <h2 className="text-sm font-medium text-gf-muted">{t('settings.embeddings')}</h2>

      {/* Backend selector */}
      <label className="block text-sm">
        {t('settings.embeddingBackend')}
        <select
          className={inputCls}
          value={form.embedding_backend}
          onChange={(e) => set('embedding_backend', e.target.value)}
        >
          {EMBEDDING_BACKENDS.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
      </label>

      {/* Model name for the active backend */}
      {backend === 'onnx' && (
        <label className="block text-sm">
          {t('settings.onnxModelName')}
          <input
            className={inputCls}
            value={form.onnx_model_name}
            onChange={(e) => set('onnx_model_name', e.target.value)}
            placeholder="sentence-transformers/all-MiniLM-L6-v2"
          />
        </label>
      )}
      {backend === 'sentence-transformers' && (
        <label className="block text-sm">
          {t('settings.stModelName')}
          <input
            className={inputCls}
            value={form.st_model_name}
            onChange={(e) => set('st_model_name', e.target.value)}
            placeholder="sentence-transformers/all-MiniLM-L6-v2"
          />
        </label>
      )}

      {/* Active space id badge */}
      {activeSpaceId && (
        <p className="text-xs text-gf-muted">
          {t('settings.activeSpaceId')}: <code className="font-mono">{activeSpaceId}</code>
        </p>
      )}

      {/* Hub model list */}
      {isDense && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-gf-muted">{t('settings.hubModels')}</p>
          {filteredModels.length === 0 ? (
            <p className="text-xs text-gf-muted">{t('settings.noHubModels')}</p>
          ) : (
            <div className="space-y-1">
              {filteredModels.map((m) => (
                <div
                  key={m.id}
                  className="flex items-center justify-between gap-3 rounded-md border border-gf-border bg-gf-bg px-3 py-2 text-sm"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{m.name}</div>
                    <div className="flex gap-2 text-xs text-gf-muted">
                      <span>{formatBytes(m.size_bytes)}</span>
                      <span className={m.downloaded ? 'text-green-600' : 'text-gf-muted'}>
                        {m.downloaded ? t('settings.downloaded') : t('settings.notDownloaded')}
                      </span>
                      {m.space_id && (
                        <span className="font-mono text-[10px]">{m.space_id}</span>
                      )}
                    </div>
                  </div>
                  {!m.downloaded && (
                    <button
                      type="button"
                      disabled={offline || downloadingId === m.name}
                      onClick={() =>
                        handleDownload(m.name, m.backend as 'st' | 'onnx')
                      }
                      className="shrink-0 flex items-center gap-1 rounded-md border border-gf-border px-2 py-1 text-xs hover:bg-gf-border disabled:opacity-50"
                    >
                      <Download className="size-3" />
                      {downloadingId === m.name
                        ? t('settings.downloading')
                        : t('settings.download')}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
          {offline && (
            <p className="text-xs text-gf-err">{t('settings.offlineHint')}</p>
          )}
        </div>
      )}
    </section>
  )
}

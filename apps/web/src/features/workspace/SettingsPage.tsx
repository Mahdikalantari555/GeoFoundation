import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { FolderOpen, Save } from 'lucide-react'
import { ApiError } from '@/api/client'
import type { UpdateSettingsRequest, WorkspaceSettings } from '@/api/workspace'
import { useUpdateSettings, useWorkspace } from './hooks'

const DEFAULT_KEY_ENV = 'GEOMEMORY_LLM_API_KEY'

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
        // Compose with any existing parent path; paste the full path to override.
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
        <input
          ref={modelDirRef}
          type="file"
          className="hidden"
          {...{ webkitdirectory: '' }}
        />
        <input
          ref={embedDirRef}
          type="file"
          className="hidden"
          {...{ webkitdirectory: '' }}
        />
        <input
          ref={visionDirRef}
          type="file"
          className="hidden"
          {...{ webkitdirectory: '' }}
        />
      </section>

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

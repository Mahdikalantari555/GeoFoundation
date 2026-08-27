import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Download } from 'lucide-react'
import { useExportFeedback } from './hooks'

const TASK_TYPES = ['rag_eval', 'qa_eval', 'sft', 'preference'] as const

export function ReviewPage() {
  const { t } = useTranslation()
  const exportFeedback = useExportFeedback()
  const [taskType, setTaskType] = useState<string>(TASK_TYPES[0])

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <h1 className="text-2xl font-semibold">{t('nav.feedback')}</h1>

      <div className="rounded-lg border border-gf-border bg-gf-panel p-4">
        <p className="mb-4 text-sm text-gf-muted">
          Export accepted feedback examples as a downloadable JSONL dataset.
        </p>

        <div className="flex items-center gap-3">
          <select
            value={taskType}
            onChange={(e) => setTaskType(e.target.value)}
            className="rounded-md border border-gf-border bg-gf-bg px-3 py-2 text-sm outline-none focus:border-gf-accent"
          >
            {TASK_TYPES.map((tt) => (
              <option key={tt} value={tt}>
                {tt}
              </option>
            ))}
          </select>

          <button
            type="button"
            onClick={() => exportFeedback.mutate({ taskType })}
            disabled={exportFeedback.isPending}
            className="flex items-center gap-2 rounded-md bg-gf-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            <Download className="size-4" />
            {exportFeedback.isPending ? 'Exporting…' : 'Export Dataset'}
          </button>
        </div>

        {exportFeedback.isError && (
          <p className="mt-3 text-xs text-gf-err" role="alert">
            {exportFeedback.error.message}
          </p>
        )}
        {exportFeedback.isSuccess && (
          <p className="mt-3 text-xs text-green-600">Download started.</p>
        )}
      </div>
    </div>
  )
}

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Gauge } from 'lucide-react'
import { useRunEval } from './hooks'

export function EvalPage() {
  const { t } = useTranslation()
  const runEval = useRunEval()
  const [benchmarkPath, setBenchmarkPath] = useState('')
  const [config, setConfig] = useState('')

  function submit() {
    if (!benchmarkPath) return
    runEval.mutate({ benchmarkPath, config: config || undefined })
  }

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <h1 className="text-2xl font-semibold">{t('nav.eval')}</h1>

      <div className="rounded-lg border border-gf-border bg-gf-panel p-4">
        <p className="mb-4 text-sm text-gf-muted">
          Run a benchmark (JSONL) against the active workspace.
        </p>

        <div className="space-y-3">
          <input
            value={benchmarkPath}
            onChange={(e) => setBenchmarkPath(e.target.value)}
            placeholder="Benchmark JSONL path"
            className="w-full rounded-md border border-gf-border bg-gf-bg px-3 py-2 text-sm outline-none focus:border-gf-accent"
          />
          <input
            value={config}
            onChange={(e) => setConfig(e.target.value)}
            placeholder="Config JSON path (optional)"
            className="w-full rounded-md border border-gf-border bg-gf-bg px-3 py-2 text-sm outline-none focus:border-gf-accent"
          />
          <button
            type="button"
            onClick={submit}
            disabled={!benchmarkPath || runEval.isPending}
            className="flex items-center gap-2 rounded-md bg-gf-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            <Gauge className="size-4" />
            {runEval.isPending ? 'Running…' : 'Run Benchmark'}
          </button>
        </div>

        {runEval.isSuccess && (
          <div className="mt-4 rounded-md bg-green-50 p-3">
            <p className="text-sm font-medium text-green-800">
              Benchmark: {runEval.data.name}
            </p>
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs text-green-700">
              {JSON.stringify(runEval.data.metrics, null, 2)}
            </pre>
          </div>
        )}
        {runEval.isError && (
          <p className="mt-3 text-xs text-gf-err" role="alert">
            {runEval.error.message}
          </p>
        )}
      </div>
    </div>
  )
}

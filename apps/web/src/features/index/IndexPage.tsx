import { useTranslation } from 'react-i18next'
import { Database, RefreshCw } from 'lucide-react'
import { useBuildIndex, useRebuildIndex } from './hooks'

export function IndexPage() {
  const { t } = useTranslation()
  const build = useBuildIndex()
  const rebuild = useRebuildIndex()

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <h1 className="text-2xl font-semibold">{t('nav.index')}</h1>

      <div className="rounded-lg border border-gf-border bg-gf-panel p-4">
        <p className="mb-4 text-sm text-gf-muted">
          Build or rebuild the retrieval index for the active embedding space.
        </p>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => build.mutate()}
            disabled={build.isPending || rebuild.isPending}
            className="flex items-center gap-2 rounded-md bg-gf-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            <Database className="size-4" />
            {build.isPending ? 'Building…' : 'Build Index'}
          </button>

          <button
            type="button"
            onClick={() => rebuild.mutate()}
            disabled={build.isPending || rebuild.isPending}
            className="flex items-center gap-2 rounded-md border border-gf-border px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            <RefreshCw className="size-4" />
            {rebuild.isPending ? 'Rebuilding…' : 'Rebuild Index'}
          </button>
        </div>

        {build.isSuccess && (
          <p className="mt-3 text-xs text-green-600">
            Built index for space: {build.data.space_id}
          </p>
        )}
        {build.isError && (
          <p className="mt-3 text-xs text-gf-err" role="alert">
            {build.error.message}
          </p>
        )}
        {rebuild.isSuccess && (
          <p className="mt-3 text-xs text-green-600">
            Rebuilt index for space: {rebuild.data.space_id}
          </p>
        )}
        {rebuild.isError && (
          <p className="mt-3 text-xs text-gf-err" role="alert">
            {rebuild.error.message}
          </p>
        )}
      </div>
    </div>
  )
}

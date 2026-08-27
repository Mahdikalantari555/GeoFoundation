import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, Archive, Files } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  useArchiveCollection,
  useCollections,
  useCreateCollection,
} from './hooks'
import { ApiError } from '@/api/client'

export function CollectionsPage() {
  const { t } = useTranslation()
  const { data: collections, isLoading, error: loadError } = useCollections()
  const create = useCreateCollection()
  const archive = useArchiveCollection()
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)

  function submit() {
    setError(null)
    create.mutate(
      { name, description: description || undefined },
      {
        onSuccess: () => {
          setShowForm(false)
          setName('')
          setDescription('')
        },
        onError: (e) => setError(e instanceof ApiError ? e.message : String(e)),
      }
    )
  }

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t('collections.title')}</h1>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-1.5 rounded-md bg-gf-accent px-3 py-2 text-sm font-medium text-white"
        >
          <Plus className="size-4" /> {t('collections.new')}
        </button>
      </div>

      {showForm && (
        <div className="space-y-3 rounded-lg border border-gf-border bg-gf-panel p-4" data-testid="collection-form">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t('collections.namePlaceholder')}
            className="w-full rounded-md border border-gf-border bg-gf-bg px-3 py-2 text-sm outline-none focus:border-gf-accent"
            data-testid="collection-name"
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t('collections.descriptionPlaceholder')}
            className="w-full rounded-md border border-gf-border bg-gf-bg px-3 py-2 text-sm outline-none focus:border-gf-accent"
          />
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={submit}
              disabled={!name || create.isPending}
              className="rounded-md bg-gf-accent px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            >
              {t('common.create')}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="rounded-md border border-gf-border px-4 py-1.5 text-sm"
            >
              {t('common.cancel')}
            </button>
            {error && (
              <span className="text-xs text-gf-err" role="alert">
                {error}
              </span>
            )}
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="py-10 text-center text-sm text-gf-muted" aria-live="polite">{t('common.loading')}</p>
      ) : loadError ? (
        <p className="rounded-md border border-gf-err/30 bg-gf-err/10 px-3 py-3 text-sm text-gf-err" role="alert">
          {loadError instanceof Error ? loadError.message : String(loadError)}
        </p>
      ) : !collections || collections.length === 0 ? (
        <p className="py-10 text-center text-sm text-gf-muted">{t('collections.empty')}</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {collections.map((col) => (
            <div
              key={col.id}
              className="flex flex-col gap-3 rounded-lg border border-gf-border bg-gf-panel p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h2 className="truncate font-medium">{col.name}</h2>
                  <p className="mt-0.5 line-clamp-2 min-h-8 text-xs text-gf-muted">
                    {col.description || '—'}
                  </p>
                </div>
                <button
                  type="button"
                  aria-label={t('collections.archive')}
                  onClick={() => {
                    if (confirm(t('collections.archiveConfirm', { name: col.name }))) {
                      archive.mutate(col.id)
                    }
                  }}
                  title={t('collections.archive')}
                  className="rounded-md border border-gf-border p-1.5 text-gf-muted transition-colors hover:border-gf-err hover:text-gf-err"
                >
                  <Archive className="size-4" aria-hidden="true" />
                </button>
              </div>
              <Link
                to={`/assets?collection=${col.id}`}
                className="flex items-center gap-1.5 text-xs font-medium text-gf-accent hover:underline"
              >
                <Files className="size-3.5" /> {t('collections.viewAssets')}
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

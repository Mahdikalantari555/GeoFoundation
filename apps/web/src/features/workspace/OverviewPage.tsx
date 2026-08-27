import { useTranslation } from 'react-i18next'
import { Database, Folder, Layers, HardDrive } from 'lucide-react'
import { useAssets, useCollections } from '@/features/knowledge/hooks'
import { useWorkspace, useWorkspaceStats } from './hooks'

export function OverviewPage() {
  const { t } = useTranslation()
  const { data: ws } = useWorkspace()
  const { data: stats } = useWorkspaceStats()
  const { data: collections } = useCollections()
  const { data: assets } = useAssets()

  const isOpen = ws?.status === 'open'

  const cards = [
    { icon: Folder, label: t('overview.collections'), value: collections?.length ?? '—' },
    { icon: Layers, label: t('overview.assets'), value: assets?.length ?? '—' },
    {
      icon: Database,
      label: t('overview.segments'),
      value: typeof stats?.segment_count === 'number' ? stats.segment_count : '—',
    },
    {
      icon: HardDrive,
      label: t('overview.storage'),
      value: typeof stats?.storage_bytes === 'number' ? `${(stats.storage_bytes / 1_048_576).toFixed(1)} MB` : '—',
    },
  ]

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t('overview.title')}</h1>
        <span
          className="rounded-full border border-gf-border px-2.5 py-0.5 text-xs text-gf-muted"
          data-testid="workspace-status"
        >
          {isOpen ? ws?.settings?.name ?? t('workspaceOpen') : t('workspaceClosed')}
        </span>
      </div>

      {!isOpen ? (
        <p className="rounded-lg border border-gf-border bg-gf-panel p-4 text-sm text-gf-muted">
          {t('settings.llmKeyHint')}
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {cards.map(({ icon: Icon, label, value }) => (
            <div key={label} className="rounded-lg border border-gf-border bg-gf-panel p-4">
              <Icon className="size-5 text-gf-accent" />
              <p className="mt-2 text-2xl font-semibold">{value}</p>
              <p className="text-xs text-gf-muted">{label}</p>
            </div>
          ))}
        </div>
      )}

      {isOpen && (
        <div className="rounded-lg border border-gf-border bg-gf-panel p-4">
          <h2 className="mb-2 text-sm font-medium text-gf-muted">{t('overview.rawStats')}</h2>
          <pre className="max-h-72 overflow-auto rounded-md bg-gf-bg p-3 text-xs">
            {JSON.stringify(stats ?? {}, null, 2)}
          </pre>
          <p className="mt-2 text-xs text-gf-muted">{t('overview.feedbackHint')}</p>
        </div>
      )}
    </div>
  )
}

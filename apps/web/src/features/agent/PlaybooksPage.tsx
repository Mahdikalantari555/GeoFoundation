import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { BookOpen, AlertTriangle, CheckCircle } from 'lucide-react'
import { agentApi, type PlaybookSummary } from '@/api/agent'

export function PlaybooksPage() {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['agent', 'playbooks'],
    queryFn: agentApi.listPlaybooks,
  })

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <h1 className="text-2xl font-semibold">{t('agent.playbooks.title', 'Playbooks')}</h1>

      {isLoading && <p className="text-sm text-gf-muted">{t('common.loading', 'Loading…')}</p>}
      {error && (
        <p className="text-sm text-gf-err" role="alert">
          {error instanceof Error ? error.message : String(error)}
        </p>
      )}

      {data?.playbooks.length === 0 && (
        <p className="text-sm text-gf-muted">
          {t('agent.playbooks.empty', 'No playbooks yet. Create one from the workspace playbooks/ folder.')}
        </p>
      )}

      <div className="space-y-3">
        {data?.playbooks.map((pb: PlaybookSummary) => (
          <div
            key={pb.name}
            className="rounded-lg border border-gf-border bg-gf-panel p-4"
          >
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BookOpen className="size-4 text-gf-accent" />
                <h3 className="text-sm font-semibold">{pb.name}</h3>
                <span className="text-xs text-gf-muted">v{pb.version}</span>
              </div>
              {pb.valid ? (
                <span className="flex items-center gap-1 text-xs text-green-600">
                  <CheckCircle className="size-3.5" /> {t('agent.playbooks.valid', 'valid')}
                </span>
              ) : (
                <span className="flex items-center gap-1 text-xs text-red-600">
                  <AlertTriangle className="size-3.5" /> {t('agent.playbooks.invalid', 'invalid')}
                </span>
              )}
            </div>

            <p className="mb-2 text-xs text-gf-muted">
              {t('agent.playbooks.steps', 'Steps')}: {pb.steps.map((s) => s.tool).join(' → ')}
            </p>

            {pb.triggers.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-1">
                {pb.triggers.map((trigger, i) => (
                  <span
                    key={i}
                    className="rounded-full border border-gf-border px-2 py-0.5 text-[11px] text-gf-muted"
                  >
                    {trigger}
                  </span>
                ))}
              </div>
            )}

            {pb.problems.length > 0 && (
              <ul className="space-y-1 text-xs text-red-600">
                {pb.problems.map((p, i) => (
                  <li key={i}>• {p}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

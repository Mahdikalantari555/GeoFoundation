import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import { cn } from '@/lib/utils'

export function HealthPill() {
  const { t } = useTranslation()
  const { data, isError } = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 10_000,
    retry: false,
  })

  const up = !isError && data?.status === 'ok'
  const wsOpen = up && data.workspace.status === 'open'
  const llmOk = up && data.llm.key_configured

  return (
    <div className="flex items-center gap-1.5 text-xs" data-testid="health-pill">
      <Pill tone={up ? 'ok' : 'err'} title={up ? t('health.gatewayUp') : t('health.gatewayDown')}>
        {up ? t('health.gatewayUp') : t('health.gatewayDown')}
      </Pill>
      {up && (
        <Pill tone={wsOpen ? 'ok' : 'warn'} title={t('health.version', { version: data.version })}>
          {wsOpen ? t('health.workspaceOpen') : t('health.workspaceClosed')}
        </Pill>
      )}
      {up && (
        <Pill tone={llmOk ? 'ok' : 'warn'}>
          {llmOk ? t('health.llmConfigured') : t('health.llmMissing')}
        </Pill>
      )}
    </div>
  )
}

function Pill({
  tone,
  title,
  children,
}: {
  tone: 'ok' | 'warn' | 'err'
  title?: string
  children: React.ReactNode
}) {
  return (
    <span
      title={title}
      className={cn(
        'rounded-full border px-2 py-0.5 font-medium whitespace-nowrap',
        tone === 'ok' && 'border-gf-ok/40 bg-gf-ok/10 text-gf-ok',
        tone === 'warn' && 'border-gf-warn/40 bg-gf-warn/10 text-gf-warn',
        tone === 'err' && 'border-gf-err/40 bg-gf-err/10 text-gf-err'
      )}
    >
      {children}
    </span>
  )
}

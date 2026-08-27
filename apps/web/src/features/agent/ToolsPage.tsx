import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Wrench, Clock, Database } from 'lucide-react'
import { agentApi, type AgentTool } from '@/api/agent'

export function ToolsPage() {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['agent', 'tools'],
    queryFn: agentApi.listTools,
  })

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <h1 className="text-2xl font-semibold">{t('agent.tools.title', 'Agent Tools')}</h1>

      {isLoading && <p className="text-sm text-gf-muted">{t('common.loading', 'Loading…')}</p>}
      {error && (
        <p className="text-sm text-gf-err" role="alert">
          {error instanceof Error ? error.message : String(error)}
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {data?.tools.map((tool: AgentTool) => (
          <div
            key={tool.name}
            className="rounded-lg border border-gf-border bg-gf-panel p-4"
          >
            <div className="mb-2 flex items-center gap-2">
              <Wrench className="size-4 text-gf-accent" />
              <h3 className="text-sm font-semibold">{tool.name}</h3>
            </div>
            <p className="mb-3 text-xs text-gf-muted">{tool.description}</p>
            <div className="flex items-center gap-3 text-[11px] text-gf-muted">
              <span className="flex items-center gap-1">
                <Clock className="size-3" /> {tool.timeout_s}s
              </span>
              {tool.cacheable && (
                <span className="flex items-center gap-1">
                  <Database className="size-3" /> {t('agent.tools.cacheable', 'cacheable')}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

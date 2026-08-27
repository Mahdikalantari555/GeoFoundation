import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { MessageSquare, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { agentApi, type ConversationSummary } from '@/api/agent'

export function ConversationsPage() {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['agent', 'conversations'],
    queryFn: agentApi.listConversations,
  })

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <h1 className="text-2xl font-semibold">{t('agent.conversations.title', 'Conversations')}</h1>

      {isLoading && <p className="text-sm text-gf-muted">{t('common.loading', 'Loading…')}</p>}
      {error && (
        <p className="text-sm text-gf-err" role="alert">
          {error instanceof Error ? error.message : String(error)}
        </p>
      )}

      {data?.conversations.length === 0 && (
        <p className="text-sm text-gf-muted">{t('agent.conversations.empty', 'No conversations yet.')}</p>
      )}

      <div className="space-y-2">
        {data?.conversations.map((conv: ConversationSummary) => (
          <Link
            key={conv.id}
            to={`/agent?conversation=${conv.id}`}
            className="flex items-center justify-between rounded-lg border border-gf-border bg-gf-panel p-4 transition-colors hover:border-gf-accent"
          >
            <div className="flex items-center gap-3">
              <MessageSquare className="size-5 text-gf-muted" />
              <div>
                <p className="text-sm font-medium">{conv.title}</p>
                <p className="text-xs text-gf-muted">{conv.created_at}</p>
              </div>
            </div>
            <ChevronRight className="size-4 text-gf-muted" />
          </Link>
        ))}
      </div>
    </div>
  )
}

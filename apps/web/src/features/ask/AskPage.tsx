import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Send, ShieldAlert, BookOpen, X } from 'lucide-react'
import type { AskMode, QAResult } from '@/api/search'
import { askApi } from '@/api/search'
import { ApiError } from '@/api/client'
import { useWorkspace } from '@/features/workspace/hooks'

type Message =
  | { id: number; role: 'user'; text: string }
  | { id: number; role: 'assistant'; qa: QAResult }

const MODES: AskMode[] = ['grounded_qa', 'research', 'code']

export function AskPage() {
  const { t } = useTranslation()
  const { data: ws } = useWorkspace()
  const isOpen = ws?.status === 'open'

  const [messages, setMessages] = useState<Message[]>([])
  const [mode, setMode] = useState<AskMode>('grounded_qa')
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sourcesOf, setSourcesOf] = useState<QAResult | null>(null)
  const idRef = useRef(0)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [messages, pending])

  function send() {
    const question = input.trim()
    if (!question || pending || !isOpen) return
    idRef.current += 1
    const userMsg: Message = { id: idRef.current, role: 'user', text: question }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setPending(true)
    setError(null)

    askApi
      .ask({ question, mode })
      .then((qa) => {
        idRef.current += 1
        setMessages((prev) => [...prev, { id: idRef.current, role: 'assistant', qa }])
      })
      .catch((e: unknown) =>
        setError(e instanceof ApiError ? e.message : String(e))
      )
      .finally(() => setPending(false))
  }

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t('ask.title')}</h1>
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as AskMode)}
          aria-label={t('ask.modeLabel')}
          disabled={pending}
          className="rounded-md border border-gf-border bg-gf-panel px-2 py-1.5 text-xs"
          data-testid="ask-mode"
        >
          {MODES.map((m) => (
            <option key={m} value={m}>
              {t(`ask.modes.${m}`)}
            </option>
          ))}
        </select>
      </div>

      <div
        className="min-h-64 flex-1 space-y-3 overflow-y-auto rounded-lg border border-gf-border bg-gf-panel p-4"
        data-testid="chat-log"
      >
        {messages.length === 0 && !pending && (
          <p className="py-16 text-center text-sm text-gf-muted">{t('ask.emptyChat')}</p>
        )}

        {messages.map((m) =>
          m.role === 'user' ? (
            <div key={m.id} className="flex justify-end" data-testid="msg-user">
              <div className="max-w-[80%] rounded-2xl rounded-ee-sm bg-gf-accent px-4 py-2 text-sm text-white whitespace-pre-wrap">
                {m.text}
              </div>
            </div>
          ) : (
            <AssistantMessage key={m.id} qa={m.qa} onShowSources={() => setSourcesOf(m.qa)} />
          )
        )}

        {pending && (
          <p className="text-sm text-gf-muted" data-testid="ask-pending">
            {t('ask.thinking')}
          </p>
        )}
        <div ref={bottomRef} />
      </div>

      {error && (
        <p className="text-xs text-gf-err" role="alert" data-testid="ask-error">
          {error}
        </p>
      )}

      <div className="flex items-center gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()}
          placeholder={t('ask.placeholder')}
          disabled={!isOpen || pending}
          className="min-w-0 flex-1 rounded-md border border-gf-border bg-gf-panel px-3 py-2.5 text-sm outline-none focus:border-gf-accent disabled:opacity-50"
          data-testid="ask-input"
        />
        <button
          type="button"
          onClick={send}
          disabled={!isOpen || pending || !input.trim()}
          className="flex items-center gap-1.5 rounded-md bg-gf-accent px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          data-testid="ask-send"
        >
          <Send className="size-4" /> {t('ask.send')}
        </button>
      </div>

      {!isOpen && (
        <p className="text-center text-xs text-gf-muted">{t('search.closedWorkspace')}</p>
      )}

      {sourcesOf && <SourcesDrawer qa={sourcesOf} onClose={() => setSourcesOf(null)} />}
    </div>
  )
}

function AssistantMessage({ qa, onShowSources }: { qa: QAResult; onShowSources: () => void }) {
  const { t } = useTranslation()

  if (qa.abstained) {
    return (
      <div className="flex justify-start" data-testid="abstention-card">
        <div className="max-w-[90%] space-y-1 rounded-2xl rounded-es-sm border border-gf-warn/50 bg-gf-warn/10 px-4 py-3">
          <p className="flex items-center gap-1.5 text-sm font-medium text-gf-warn">
            <ShieldAlert className="size-4" /> {t('ask.abstainedTitle')}
          </p>
          {qa.abstention_reason && (
            <p className="text-xs text-gf-muted">{qa.abstention_reason}</p>
          )}
          <p className="text-xs text-gf-muted">{t('ask.configureHint')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start" data-testid="msg-assistant">
      <div className="max-w-[90%] space-y-2 rounded-2xl rounded-es-sm border border-gf-border bg-gf-bg px-4 py-3">
        <p className="whitespace-pre-wrap text-sm">{qa.text}</p>
        {qa.citations.length > 0 && (
          <div className="space-y-1.5" data-testid="citations">
            <p className="flex items-center gap-1 text-xs font-medium text-gf-muted">
              <BookOpen className="size-3.5" /> {t('ask.citations')}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {qa.citations.map((cit, i) => (
                <button
                  key={cit.id}
                  type="button"
                  onClick={onShowSources}
                  title={JSON.stringify(cit.locator)}
                  className="rounded-full border border-gf-border px-2 py-0.5 text-[11px] text-gf-accent hover:bg-gf-accent-soft"
                  data-testid={`citation-${i}`}
                >
                  S{i + 1} · {cit.segment_id.slice(0, 12)}…
                </button>
              ))}
            </div>
          </div>
        )}
        {(qa.citations.length > 0 || qa.sources.length > 0) && (
          <button
            type="button"
            onClick={onShowSources}
            className="text-xs font-medium text-gf-accent hover:underline"
          >
            {t('ask.showSources', { count: Math.max(qa.sources.length, qa.citations.length) })}
          </button>
        )}
      </div>
    </div>
  )
}

function SourcesDrawer({ qa, onClose }: { qa: QAResult; onClose: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={onClose}>
      <div
        className="h-full w-full max-w-lg overflow-y-auto border-s border-gf-border bg-gf-panel p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        data-testid="sources-drawer"
      >
        <div className="mb-4 flex items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">
            {t('ask.sourcesTitle')} ({qa.sources.length})
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('common.cancel')}
            className="rounded-md border border-gf-border p-1.5 text-gf-muted hover:text-gf-text"
          >
            <X className="size-4" />
          </button>
        </div>

        {qa.model && (
          <p className="mb-3 text-xs text-gf-muted">model: {qa.model}</p>
        )}

        <ul className="space-y-3">
          {qa.sources.map((s, i) => (
            <li key={s.id} className="rounded-lg border border-gf-border p-3" data-testid="source-item">
              <p className="mb-1 text-xs font-medium text-gf-muted">
                S{i + 1} · score {s.score.toFixed(3)}
              </p>
              <p className="line-clamp-6 whitespace-pre-wrap text-sm">{s.text}</p>
            </li>
          ))}
          {qa.sources.length === 0 && (
            <li className="text-sm text-gf-muted">{t('search.noResults')}</li>
          )}
        </ul>
      </div>
    </div>
  )
}

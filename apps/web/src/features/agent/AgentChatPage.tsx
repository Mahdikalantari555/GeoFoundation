import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Send, Wrench, Loader2 } from 'lucide-react'
import { useWorkspace } from '@/features/workspace/hooks'

type AgentMessage = {
  id: number
  role: 'user' | 'assistant'
  text: string
  toolRuns?: { tool: string; status: string }[]
}

export function AgentChatPage() {
  const { t } = useTranslation()
  const { data: ws } = useWorkspace()
  const isOpen = ws?.status === 'open'

  const [messages, setMessages] = useState<AgentMessage[]>([])
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const idRef = useRef(0)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [messages, pending])

  function send() {
    const message = input.trim()
    if (!message || pending || !isOpen) return
    idRef.current += 1
    const userMsg: AgentMessage = { id: idRef.current, role: 'user', text: message }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setPending(true)
    setError(null)

    const convId = undefined
    fetch('/api/v1/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, conversation_id: convId }),
    })
      .then(async (resp) => {
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}))
          throw new Error(err.error?.message || `HTTP ${resp.status}`)
        }
        const reader = resp.body?.getReader()
        if (!reader) throw new Error('No response body')
        const decoder = new TextDecoder()
        let buffer = ''

        let currentText = ''
        const toolRuns: { tool: string; status: string }[] = []

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (!line.trim()) continue
            if (line.startsWith(': ping')) continue

            const eventMatch = line.match(/^event: (.+)$/m)
            const dataMatch = line.match(/^data: (.+)$/m)
            if (!eventMatch || !dataMatch) continue

            const event = eventMatch[1]
            const data = JSON.parse(dataMatch[1])

            if (event === 'message') {
              if (data.final) {
                currentText = data.text
              } else if (data.text) {
                currentText += data.text
              }
            } else if (event === 'tool_start') {
              toolRuns.push({ tool: data.tool, status: 'running' })
            } else if (event === 'tool_end') {
              const tr = toolRuns.find((r) => r.tool === data.tool && r.status === 'running')
              if (tr) tr.status = data.status
            } else if (event === 'done') {
              idRef.current += 1
              setMessages((prev) => [
                ...prev,
                { id: idRef.current, role: 'assistant', text: currentText, toolRuns: [...toolRuns] },
              ])
              currentText = ''
              toolRuns.length = 0
            } else if (event === 'error') {
              throw new Error(data.message)
            }
          }
        }
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setPending(false))
  }

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col space-y-4">
      <h1 className="text-2xl font-semibold">{t('agent.chat.title', 'Agent Chat')}</h1>

      <div
        className="min-h-64 flex-1 space-y-3 overflow-y-auto rounded-lg border border-gf-border bg-gf-panel p-4"
        data-testid="agent-chat-log"
      >
        {messages.length === 0 && !pending && (
          <p className="py-16 text-center text-sm text-gf-muted">
            {t('agent.chat.empty', 'Start a conversation with the agent.')}
          </p>
        )}

        {messages.map((m) =>
          m.role === 'user' ? (
            <div key={m.id} className="flex justify-end" data-testid="msg-user">
              <div className="max-w-[80%] rounded-2xl rounded-ee-sm bg-gf-accent px-4 py-2 text-sm text-white whitespace-pre-wrap">
                {m.text}
              </div>
            </div>
          ) : (
            <div key={m.id} className="flex justify-start" data-testid="msg-assistant">
              <div className="max-w-[90%] space-y-2 rounded-2xl rounded-es-sm border border-gf-border bg-gf-bg px-4 py-3">
                <p className="whitespace-pre-wrap text-sm">{m.text}</p>
                {m.toolRuns && m.toolRuns.length > 0 && (
                  <div className="space-y-1" data-testid="tool-runs">
                    <p className="flex items-center gap-1 text-xs font-medium text-gf-muted">
                      <Wrench className="size-3.5" /> {t('agent.toolsUsed', 'Tools used')}
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {m.toolRuns.map((tr, i) => (
                        <span
                          key={i}
                          className="rounded-full border border-gf-border px-2 py-0.5 text-[11px] text-gf-muted"
                        >
                          {tr.tool} · {tr.status}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )
        )}

        {pending && (
          <p className="text-sm text-gf-muted" data-testid="agent-pending">
            <Loader2 className="inline size-3 animate-spin" /> {t('agent.thinking', 'Thinking…')}
          </p>
        )}
        <div ref={bottomRef} />
      </div>

      {error && (
        <p className="text-xs text-gf-err" role="alert" data-testid="agent-error">
          {error}
        </p>
      )}

      <div className="flex items-center gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()}
          placeholder={t('agent.placeholder', 'Ask the agent…')}
          disabled={!isOpen || pending}
          className="min-w-0 flex-1 rounded-md border border-gf-border bg-gf-panel px-3 py-2.5 text-sm outline-none focus:border-gf-accent disabled:opacity-50"
          data-testid="agent-input"
        />
        <button
          type="button"
          onClick={send}
          disabled={!isOpen || pending || !input.trim()}
          className="flex items-center gap-1.5 rounded-md bg-gf-accent px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          data-testid="agent-send"
        >
          <Send className="size-4" /> {t('agent.send', 'Send')}
        </button>
      </div>

      {!isOpen && (
        <p className="text-center text-xs text-gf-muted">{t('search.closedWorkspace')}</p>
      )}
    </div>
  )
}

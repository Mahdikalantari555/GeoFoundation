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
  const [error, setError] = useState<{ message: string; code?: string } | null>(null)
  const [lastMessage, setLastMessage] = useState<string>('')
  const abortRef = useRef<AbortController | null>(null)
  const idRef = useRef(0)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [messages, pending])

  function abort() {
    abortRef.current?.abort()
    setPending(false)
    setError({ message: 'Cancelled', code: 'cancelled' })
  }

  function send(retryMsg?: string) {
    const message = (retryMsg ?? input).trim()
    if (!message || pending) return
    if (!isOpen) {
      setError({ message: 'Agent not initialized. Open a workspace first.', code: 'agent_not_ready' })
      return
    }
    idRef.current += 1
    const userMsg: AgentMessage = { id: idRef.current, role: 'user', text: message }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLastMessage(message)
    setPending(true)
    setError(null)

    const convId = undefined
    const controller = new AbortController()
    abortRef.current = controller
    fetch('/api/v1/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, conversation_id: convId }),
      signal: controller.signal,
    })
      .then(async (resp) => {
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}))
          const e = err.error ?? {}
          const code = e.code ?? (resp.status === 409 ? 'agent_not_ready' : 'http_error')
          const msg = e.message ?? `HTTP ${resp.status}`
          const error = new Error(msg) as Error & { code?: string; detail?: unknown }
          error.code = code
          ;(error as unknown as Record<string, unknown>).detail = e.detail
          throw error
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
              const err = new Error(data.message ?? 'Agent error') as Error & { code?: string }
              err.code = data.code ?? 'internal_error'
              throw err
            }
          }
        }
      })
      .catch((e: unknown) => {
        if ((e as Error).name === 'AbortError') {
          setError({ message: 'Cancelled', code: 'cancelled' })
        } else {
          const code = (e as unknown as { code?: string })?.code
          setError({ message: e instanceof Error ? e.message : String(e), code })
        }
      })
      .finally(() => {
        setPending(false)
        abortRef.current = null
      })
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
        <div className="flex items-center justify-between gap-3 rounded-lg border border-gf-err/50 bg-gf-err/10 px-3 py-2 text-sm" role="alert" data-testid="agent-error">
          <div>
            <p className="font-medium text-gf-err">{error.code ? `${error.code}: ` : ''}{error.message}</p>
            {error.code === 'agent_not_ready' && <p className="text-xs text-gf-muted">Open a workspace to enable the agent.</p>}
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => error.code === 'cancelled' ? setError(null) : send(lastMessage)} className="rounded border border-gf-border px-2 py-1 text-xs">
              {error.code === 'cancelled' ? 'Dismiss' : 'Retry'}
            </button>
          </div>
        </div>
      )}

      {!isOpen && (
        <div className="rounded-lg border border-gf-warn/50 bg-gf-warn/10 p-3 text-sm" role="alert" data-testid="agent-not-ready">
          <p className="font-medium text-gf-warn">Agent not ready — no workspace open</p>
          <p className="text-xs text-gf-muted">Open a workspace to start chatting. <span className="font-mono">409 agent_not_ready</span></p>
        </div>
      )}

      <div className="flex items-center gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()}
          placeholder={t('agent.placeholder', 'Ask the agent…')}
          disabled={pending}
          className="min-w-0 flex-1 rounded-md border border-gf-border bg-gf-panel px-3 py-2.5 text-sm outline-none focus:border-gf-accent disabled:opacity-50"
          data-testid="agent-input"
        />
        {pending ? (
          <button
            type="button"
            onClick={abort}
            className="flex items-center gap-1.5 rounded-md border border-gf-err bg-gf-err/10 px-4 py-2.5 text-sm font-medium text-gf-err"
            data-testid="agent-abort"
          >
            Cancel
          </button>
        ) : (
          <button
            type="button"
            onClick={() => send()}
            disabled={!input.trim()}
            className="flex items-center gap-1.5 rounded-md bg-gf-accent px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
            data-testid="agent-send"
          >
            <Send className="size-4" /> {t('agent.send', 'Send')}
          </button>
        )}
      </div>
    </div>
  )
}

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Download } from 'lucide-react'
import { useCandidates, useProposals, useExportFeedback, useReviewCandidate, useApproveProposal, useRejectProposal } from './hooks'

const TASK_TYPES = ['rag_eval', 'qa_eval', 'sft', 'preference'] as const

export function ReviewPage() {
  const { t } = useTranslation()
  const exportFeedback = useExportFeedback()
  const [taskType, setTaskType] = useState<string>(TASK_TYPES[0])
  const [stateFilter, setStateFilter] = useState<string>('')
  const candidates = useCandidates(stateFilter || undefined)
  const proposals = useProposals()
  const review = useReviewCandidate()
  const approve = useApproveProposal()
  const reject = useRejectProposal()

  const candList = (candidates.data as unknown[]) || []
  const propList = (proposals.data as unknown[]) || []
  const pending = propList.filter((p: unknown) => (p as { status: string }).status === 'pending').length
  const approved = propList.filter((p: unknown) => (p as { status: string }).status === 'approved').length
  const rejected = propList.filter((p: unknown) => (p as { status: string }).status === 'rejected').length

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <h1 className="text-2xl font-semibold">{t('nav.feedback')}</h1>

      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-gf-border bg-gf-panel p-3 text-center"><div className="text-xs text-gf-muted">Pending</div><div className="text-xl font-semibold">{pending}</div></div>
        <div className="rounded-lg border border-gf-border bg-gf-panel p-3 text-center"><div className="text-xs text-gf-muted">Approved</div><div className="text-xl font-semibold">{approved}</div></div>
        <div className="rounded-lg border border-gf-border bg-gf-panel p-3 text-center"><div className="text-xs text-gf-muted">Rejected</div><div className="text-xl font-semibold">{rejected}</div></div>
      </div>

      <div className="rounded-lg border border-gf-border bg-gf-panel p-4">
        <h2 className="mb-2 text-sm font-semibold">Candidates</h2>
        <div className="mb-3 flex gap-2">
          <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)} className="rounded-md border border-gf-border bg-gf-bg px-2 py-1 text-xs">
            <option value="">All states</option>
            <option value="proposed">proposed</option>
            <option value="supported">supported</option>
            <option value="verified">verified</option>
            <option value="rejected">rejected</option>
          </select>
        </div>
        {!candList.length && <p className="text-xs text-gf-muted">No candidates.</p>}
        <ul className="space-y-2">
          {(candList as { id: string; content: string; state: string; confidence_score: number; memory_type: string }[]).map((c) => (
            <li key={c.id} className="rounded border border-gf-border p-3">
              <div className="flex items-center gap-2 text-xs">
                <span className="rounded bg-gf-accent px-2 py-0.5 text-white">{c.state}</span>
                <span className="rounded border border-gf-border px-2 py-0.5">{c.memory_type}</span>
                <span className="text-gf-muted">score {c.confidence_score}</span>
                <span className="ms-auto font-mono text-[10px]">{c.id.slice(0, 8)}</span>
              </div>
              <p className="mt-2 text-sm">{c.content.slice(0, 300)}</p>
              <div className="mt-2 flex gap-2">
                {c.state === 'proposed' && <button type="button" onClick={() => review.mutate({ id: c.id, new_state: 'supported' })} className="rounded bg-gf-accent px-3 py-1 text-xs text-white">Promote to Supported</button>}
                {c.state === 'supported' && <button type="button" onClick={() => review.mutate({ id: c.id, new_state: 'verified' })} className="rounded bg-gf-accent px-3 py-1 text-xs text-white">Promote to Verified</button>}
                {c.state !== 'rejected' && <button type="button" onClick={() => review.mutate({ id: c.id, new_state: 'rejected', note: 'rejected via UI' })} className="rounded border border-gf-border px-3 py-1 text-xs">Reject</button>}
              </div>
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-lg border border-gf-border bg-gf-panel p-4">
        <h2 className="mb-2 text-sm font-semibold">Proposals (diff viewer)</h2>
        {!propList.length && <p className="text-xs text-gf-muted">No proposals.</p>}
        <ul className="space-y-2">
          {(propList as { id: string; proposal_type: string; diff: { original: unknown; proposed: unknown }; status: string; confidence: number }[]).map((p) => (
            <li key={p.id} className="rounded border border-gf-border p-3">
              <div className="flex items-center gap-2 text-xs"><span className="rounded border border-gf-border px-2 py-0.5">{p.proposal_type}</span><span className="rounded bg-gf-accent px-2 py-0.5 text-white">{p.status}</span><span className="text-gf-muted">conf {p.confidence}</span></div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                <div className="rounded bg-gf-bg p-2"><div className="mb-1 font-semibold">Original</div><pre className="whitespace-pre-wrap break-words">{JSON.stringify(p.diff.original, null, 2)}</pre></div>
                <div className="rounded bg-gf-bg p-2"><div className="mb-1 font-semibold">Proposed</div><pre className="whitespace-pre-wrap break-words">{JSON.stringify(p.diff.proposed, null, 2)}</pre></div>
              </div>
              {p.status === 'pending' && <div className="mt-2 flex gap-2"><button type="button" onClick={() => approve.mutate({ id: p.id, note: 'approved via UI' })} className="rounded bg-green-600 px-3 py-1 text-xs text-white">Approve</button><button type="button" onClick={() => reject.mutate({ id: p.id, note: 'rejected via UI' })} className="rounded border border-gf-border px-3 py-1 text-xs">Reject</button></div>}
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-lg border border-gf-border bg-gf-panel p-4">
        <p className="mb-4 text-sm text-gf-muted">Export accepted feedback examples as a downloadable JSONL dataset.</p>
        <div className="flex items-center gap-3">
          <select value={taskType} onChange={(e) => setTaskType(e.target.value)} className="rounded-md border border-gf-border bg-gf-bg px-3 py-2 text-sm outline-none focus:border-gf-accent">
            {TASK_TYPES.map((tt) => (<option key={tt} value={tt}>{tt}</option>))}
          </select>
          <button type="button" onClick={() => exportFeedback.mutate({ taskType })} disabled={exportFeedback.isPending} className="flex items-center gap-2 rounded-md bg-gf-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
            <Download className="size-4" />{exportFeedback.isPending ? 'Exporting…' : 'Export Dataset'}
          </button>
        </div>
        {exportFeedback.isError && <p className="mt-3 text-xs text-gf-err" role="alert">{exportFeedback.error.message}</p>}
        {exportFeedback.isSuccess && <p className="mt-3 text-xs text-green-600">Download started.</p>}
      </div>
    </div>
  )
}

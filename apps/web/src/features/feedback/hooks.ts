import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { opsApi } from '@/api/ops'

export function useExportFeedback() {
  return useMutation({
    mutationFn: async ({ taskType }: { taskType: string }) => {
      const res = await opsApi.exportFeedback(taskType)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `feedback-${taskType}.jsonl`
      a.click()
      URL.revokeObjectURL(url)
    },
  })
}

export function useCandidates(state?: string) {
  return useQuery({ queryKey: ['candidates', state], queryFn: () => opsApi.listCandidates(state) })
}

export function useProposals(status?: string) {
  return useQuery({ queryKey: ['proposals', status], queryFn: () => opsApi.listProposals(status) })
}

export function useReviewCandidate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, new_state, note }: { id: string; new_state: string; note?: string }) => opsApi.reviewCandidate(id, new_state, undefined, note),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['candidates'] }),
  })
}

export function useApproveProposal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, note }: { id: string; note?: string }) => opsApi.approveProposal(id, undefined, note),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['proposals'] }),
  })
}

export function useRejectProposal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, note }: { id: string; note?: string }) => opsApi.rejectProposal(id, undefined, note),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['proposals'] }),
  })
}

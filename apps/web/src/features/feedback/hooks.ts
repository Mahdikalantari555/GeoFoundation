import { useMutation } from '@tanstack/react-query'
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

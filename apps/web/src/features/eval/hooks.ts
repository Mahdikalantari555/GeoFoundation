import { useMutation } from '@tanstack/react-query'
import { opsApi } from '@/api/ops'

export function useRunEval() {
  return useMutation({
    mutationFn: ({ benchmarkPath, config }: { benchmarkPath: string; config?: string }) =>
      opsApi.runEval(benchmarkPath, config),
  })
}

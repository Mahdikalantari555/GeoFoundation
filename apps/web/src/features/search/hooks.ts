import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { feedbackApi, searchApi, type FeedbackEvent, type SearchBody, type SearchResult } from '@/api/search'

export function useSearch() {
  const [result, setResult] = useState<SearchResult | null>(null)
  const mutation = useMutation({
    mutationFn: (body: SearchBody) => searchApi.run(body),
    onSuccess: (data) => setResult(data),
  })
  return { result, run: mutation.mutate, isRunning: mutation.isPending, error: mutation.error }
}

type FeedbackDirection = 'up' | 'down'

export function useHitFeedback() {
  const [given, setGiven] = useState<Record<string, FeedbackDirection>>({})
  const mutation = useMutation({
    mutationFn: (vars: {
      segmentId: string
      direction: FeedbackDirection
      query: string
    }) =>
      feedbackApi.record({
        target_type: 'segment',
        target_id: vars.segmentId,
        label: 'source_relevance',
        payload: {
          rating: vars.direction === 'up' ? 'relevant' : 'not_relevant',
          query: vars.query,
        },
      }),
    onSuccess: (_data: FeedbackEvent, vars) =>
      setGiven((prev) => ({ ...prev, [vars.segmentId]: vars.direction })),
  })
  return { given, record: mutation.mutate, isPending: mutation.isPending }
}

import { useEffect } from 'react'
import { useQueryClient, type QueryClient } from '@tanstack/react-query'

// SPEC_WEB invalidation map: SSE events refresh query caches so the UI never
// shows stale workspace state while jobs run in the background.
function invalidate(qc: QueryClient, keys: string[][]) {
  for (const key of keys) void qc.invalidateQueries({ queryKey: key })
}

/** Subscribe to gateway SSE `/events` and invalidate caches per event. */
export function useEvents() {
  const qc = useQueryClient()

  useEffect(() => {
    if (typeof EventSource === 'undefined') return // jsdom tests / very old browsers
    const es = new EventSource('/api/v1/events')

    const onJobProgress = () => invalidate(qc, [['job']])
    const onAssetCreated = () => invalidate(qc, [['assets'], ['stats']])
    const onCollectionChanged = () => invalidate(qc, [['collections'], ['stats']])
    const onWorkspaceChanged = () =>
      invalidate(qc, [['workspace'], ['stats'], ['collections'], ['assets']])

    es.addEventListener('job_progress', onJobProgress)
    es.addEventListener('asset_created', onAssetCreated)
    es.addEventListener('collection_created', onCollectionChanged)
    es.addEventListener('collection_archived', onCollectionChanged)
    es.addEventListener('workspace_changed', onWorkspaceChanged)

    return () => {
      es.removeEventListener('job_progress', onJobProgress)
      es.removeEventListener('asset_created', onAssetCreated)
      es.removeEventListener('collection_created', onCollectionChanged)
      es.removeEventListener('collection_archived', onCollectionChanged)
      es.removeEventListener('workspace_changed', onWorkspaceChanged)
      es.close()
    }
  }, [qc])
}

import { useEffect, useState } from 'react'
import { useQueryClient, type QueryClient } from '@tanstack/react-query'

// SPEC_WEB invalidation map: SSE events refresh query caches so the UI never
// shows stale workspace state while jobs run in the background.
function invalidate(qc: QueryClient, keys: string[][]) {
  for (const key of keys) void qc.invalidateQueries({ queryKey: key })
}

/** Subscribe to gateway SSE `/events` and invalidate caches per event. Returns connection error for banner. */
export function useEvents() {
  const qc = useQueryClient()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (typeof EventSource === 'undefined') return // jsdom tests / very old browsers
    let es: EventSource | null = null
    let reconnectTimer: number | null = null
    let closed = false

    function connect() {
      es = new EventSource('/api/v1/events')
      const onJobProgress = (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data)
          if (data.status === 'error' || data.status === 'failed') {
            // Surface job failure as invalidation + keep error visible via query cache
          }
        } catch {
          /* ignore */
        }
        invalidate(qc, [['job'], ['assets'], ['stats']])
      }
      const onAssetCreated = () => invalidate(qc, [['assets'], ['stats']])
      const onCollectionChanged = () => invalidate(qc, [['collections'], ['stats']])
      const onWorkspaceChanged = () =>
        invalidate(qc, [['workspace'], ['stats'], ['collections'], ['assets']])
      const onError = () => {
        setError('SSE disconnected — reconnecting…')
        es?.close()
        if (!closed) {
          reconnectTimer = window.setTimeout(connect, 3000)
        }
      }
      const onOpen = () => setError(null)

      es.addEventListener('job_progress', onJobProgress as EventListener)
      es.addEventListener('asset_created', onAssetCreated)
      es.addEventListener('collection_created', onCollectionChanged)
      es.addEventListener('collection_archived', onCollectionChanged)
      es.addEventListener('workspace_changed', onWorkspaceChanged)
      es.addEventListener('error', onError as EventListener)
      es.onopen = onOpen
      es.onerror = onError as unknown as (ev: Event) => unknown

      // store cleanup
      ;(es as unknown as Record<string, unknown>)._cleanup = () => {
        es?.removeEventListener('job_progress', onJobProgress as EventListener)
        es?.removeEventListener('asset_created', onAssetCreated)
        es?.removeEventListener('collection_created', onCollectionChanged)
        es?.removeEventListener('collection_archived', onCollectionChanged)
        es?.removeEventListener('workspace_changed', onWorkspaceChanged)
        es?.removeEventListener('error', onError as EventListener)
      }
    }

    connect()

    return () => {
      closed = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      const cleanup = (es as unknown as { _cleanup?: () => void })?._cleanup
      cleanup?.()
      es?.close()
    }
  }, [qc])

  return { error }
}

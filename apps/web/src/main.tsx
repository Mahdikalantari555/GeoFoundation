import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import { router } from './app/router'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import '@/i18n'
import '@/index.css'

function showToast(message: string) {
  // lightweight toast via console + DOM banner
  console.error('[query error]', message)
  let el = document.getElementById('global-toast')
  if (!el) {
    el = document.createElement('div')
    el.id = 'global-toast'
    el.className = 'fixed bottom-4 end-4 z-50 max-w-sm rounded-lg border border-gf-err/50 bg-gf-err/10 px-4 py-2 text-sm text-gf-err shadow-lg'
    el.setAttribute('role', 'alert')
    document.body.appendChild(el)
  }
  el.textContent = message
  el.style.display = 'block'
  setTimeout(() => {
    if (el) el.style.display = 'none'
  }, 4000)
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error) => {
      const msg = error instanceof Error ? error.message : String(error)
      const code = (error as unknown as { code?: string })?.code
      showToast(code ? `${code}: ${msg}` : msg)
    },
  }),
  defaultOptions: {
    queries: { retry: 1, staleTime: 5_000 },
    mutations: {
      onError: (error) => {
        const msg = error instanceof Error ? error.message : String(error)
        const code = (error as unknown as { code?: string })?.code
        showToast(code ? `${code}: ${msg}` : msg)
      },
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>
)

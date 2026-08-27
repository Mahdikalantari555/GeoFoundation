import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { api, type Health } from '@/api/client'
import { routes } from '@/app/router'

vi.mock('@/api/client', () => ({
  api: { health: vi.fn() },
}))

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
}

function renderApp() {
  const router = createMemoryRouter(routes, { initialEntries: ['/'] })
  return render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}

const healthy: Health = {
  status: 'ok',
  version: '0.1.0',
  workspace: { status: 'closed', path: null, name: null },
  llm: {
    provider: 'api',
    key_env: 'GEOMEMORY_LLM_API_KEY',
    key_configured: true,
    base_url: null,
  },
}

describe('AppShell', () => {
  it('renders sidebar groups and header', async () => {
    vi.mocked(api.health).mockResolvedValue(healthy)
    renderApp()

    expect(screen.getByTestId('app-shell')).toBeInTheDocument()
    expect(screen.getAllByText('Workspace').length).toBeGreaterThan(0)
    expect(screen.getByText('Knowledge')).toBeInTheDocument()
    expect(screen.getByText('Agent')).toBeInTheDocument()
    expect(screen.getByText('Geo')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Gateway online')).toBeInTheDocument()
      expect(screen.getByText('No workspace')).toBeInTheDocument()
      expect(screen.getByText('LLM configured')).toBeInTheDocument()
    })
  })

  it('shows offline pill when gateway is down', async () => {
    vi.mocked(api.health).mockRejectedValue(new Error('network'))
    renderApp()

    await waitFor(() => {
      expect(screen.getByText('Gateway offline')).toBeInTheDocument()
    })
  })
})

describe('router', () => {
  it('renders placeholder pages without crashing', async () => {
    vi.mocked(api.health).mockResolvedValue(healthy)
    const router = createMemoryRouter(routes, { initialEntries: ['/maps'] })
    render(
      <QueryClientProvider client={makeClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    )
    expect(await screen.findByText('Coming soon')).toBeInTheDocument()
  })
})

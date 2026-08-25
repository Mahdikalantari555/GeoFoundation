import '@/i18n'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { SearchResult } from '@/api/search'
import { SearchPage } from './SearchPage'

vi.mock('@/api/search', async (orig) => {
  const actual = await orig<typeof import('@/api/search')>()
  return {
    ...actual,
    searchApi: { run: vi.fn() },
    feedbackApi: { record: vi.fn() },
  }
})

vi.mock('@/features/workspace/hooks', () => ({
  useWorkspace: () => ({ data: { status: 'open' } }),
}))

vi.mock('@/features/knowledge/hooks', () => ({
  useCollections: () => ({ data: [{ id: 'col1', name: 'Papers' }] }),
  useAssets: () => ({ data: [] }),
  useAssetDetail: () => ({ data: null }),
  useCreateCollection: () => ({ mutate: vi.fn(), isPending: false }),
  useArchiveCollection: () => ({ mutate: vi.fn(), isPending: false }),
  useIngest: () => ({ mutate: vi.fn(), isPending: false }),
  useJobPolling: () => ({ data: null }),
}))

const { searchApi, feedbackApi } = await import('@/api/search')

function makeResult(): SearchResult {
  return {
    query: 'ndvi',
    query_plan: {
      intent: 'search',
      mode: 'hybrid',
      spaces: [],
      top_k: 20,
      top_n: 5,
      filters: {},
    },
    hits: [
      {
        id: 'seg_abc',
        score: 0.82,
        sparse_score: 0.7,
        dense_score: 0.9,
        metadata: { title: 'Sugarcane notes' },
        text: 'NDVI drops under water stress.',
        locator: { asset_id: 'a1' },
      },
    ],
    total_hits: 1,
    latency_ms: 12,
    retrieval_run_id: 'run_1',
  }
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <SearchPage />
    </QueryClientProvider>
  )
}

describe('SearchPage', () => {
  it('shows hint before first run and runs a search', async () => {
    vi.mocked(searchApi.run).mockResolvedValue(makeResult())
    renderPage()

    expect(screen.getByText(/Type a query/)).toBeInTheDocument()

    fireEvent.change(screen.getByTestId('search-input'), { target: { value: 'ndvi' } })
    fireEvent.click(screen.getByTestId('search-run'))

    await waitFor(() => {
      expect(screen.getAllByTestId('hit-card').length).toBe(1)
    })
    expect(screen.getByText('NDVI drops under water stress.')).toBeInTheDocument()
    expect(vi.mocked(searchApi.run)).toHaveBeenCalledWith(
      expect.objectContaining({ query: 'ndvi', mode: 'hybrid', top_n: 5 })
    )
  })

  it('switches modes and sends the selected one', async () => {
    vi.mocked(searchApi.run).mockResolvedValue(makeResult())
    renderPage()

    fireEvent.click(screen.getByTestId('mode-dense'))
    fireEvent.change(screen.getByTestId('search-input'), { target: { value: 'q' } })
    fireEvent.click(screen.getByTestId('search-run'))

    await waitFor(() => {
      expect(vi.mocked(searchApi.run)).toHaveBeenCalledWith(
        expect.objectContaining({ mode: 'dense' })
      )
    })
  })

  it('records feedback for a hit', async () => {
    vi.mocked(searchApi.run).mockResolvedValue(makeResult())
    vi.mocked(feedbackApi.record).mockResolvedValue({
      id: 'fb1',
      target_type: 'segment',
      target_id: 'seg_abc',
      actor: 'user',
      label: 'source_relevance',
      payload: {},
    })
    renderPage()

    fireEvent.change(screen.getByTestId('search-input'), { target: { value: 'ndvi' } })
    fireEvent.click(screen.getByTestId('search-run'))
    await screen.findByTestId('hit-card')

    fireEvent.click(screen.getByRole('button', { name: 'Relevant' }))
    await waitFor(() => {
      expect(vi.mocked(feedbackApi.record)).toHaveBeenCalledWith(
        expect.objectContaining({
          target_type: 'segment',
          target_id: 'seg_abc',
          label: 'source_relevance',
        })
      )
    })
  })

  it('opens filter panel and toggles spatial picker', async () => {
    renderPage()
    fireEvent.click(screen.getByTestId('filters-toggle'))
    expect(screen.getByTestId('filter-panel')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('spatial-toggle'))
    expect(screen.getByTestId('bbox-picker')).toBeInTheDocument()
  })

  it('shows empty state when there are no hits', async () => {
    vi.mocked(searchApi.run).mockResolvedValue({
      ...makeResult(),
      hits: [],
      total_hits: 0,
    })
    renderPage()
    fireEvent.change(screen.getByTestId('search-input'), { target: { value: 'nothing' } })
    fireEvent.click(screen.getByTestId('search-run'))
    await waitFor(() => {
      expect(screen.getByTestId('no-results')).toBeInTheDocument()
    })
  })
})

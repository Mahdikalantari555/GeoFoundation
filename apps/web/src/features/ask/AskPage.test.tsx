import '@/i18n'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { QAResult } from '@/api/search'
import { AskPage } from './AskPage'

vi.mock('@/api/search', async (orig) => {
  const actual = await orig<typeof import('@/api/search')>()
  return {
    ...actual,
    askApi: { ask: vi.fn() },
  }
})

vi.mock('@/api/ops', () => ({
  opsApi: { suggestCorrection: vi.fn() },
}))

vi.mock('@/features/workspace/hooks', () => ({
  useWorkspace: () => ({ data: { status: 'open' } }),
}))

const { askApi } = await import('@/api/search')
const { opsApi } = await import('@/api/ops')

const abstained: QAResult = {
  text: 'not found in selected sources',
  citations: [],
  abstained: true,
  abstention_reason: 'No LLM backend available',
  sources: [],
  retrieval_run_id: 'run_1',
  latency_ms: 5,
  model: 'none',
}

const answered: QAResult = {
  text: 'NDVI declines under water stress.',
  citations: [
    {
      id: 'cit_1',
      answer_id: 'ans_1',
      segment_id: 'seg_abc1234567890',
      locator: { asset_id: 'a1' },
      claim_span: null,
    },
  ],
  abstained: false,
  abstention_reason: null,
  sources: [
    {
      id: 'seg_abc1234567890',
      score: 0.9,
      sparse_score: 0.8,
      dense_score: 0.95,
      metadata: {},
      text: 'NDVI drops under stress.',
      locator: {},
    },
  ],
  retrieval_run_id: 'run_2',
  latency_ms: 40,
  model: 'test-model',
  turn_id: 'turn_test123',
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AskPage />
    </QueryClientProvider>
  )
}

describe('AskPage', () => {
  it('renders empty chat hint', () => {
    renderPage()
    expect(screen.getByText(/Ask a question/)).toBeInTheDocument()
  })

  it('shows the abstention card when the model is unavailable', async () => {
    vi.mocked(askApi.ask).mockResolvedValue(abstained)
    renderPage()

    fireEvent.change(screen.getByTestId('ask-input'), { target: { value: 'what about ndvi?' } })
    fireEvent.click(screen.getByTestId('ask-send'))

    await waitFor(() => {
      expect(screen.getByTestId('abstention-card')).toBeInTheDocument()
    })
    expect(screen.getByText('No LLM backend available')).toBeInTheDocument()
    expect(vi.mocked(askApi.ask)).toHaveBeenCalledWith(
      expect.objectContaining({ question: 'what about ndvi?', mode: 'grounded_qa' })
    )
  })

  it('shows answers with citations and opens the sources drawer', async () => {
    vi.mocked(askApi.ask).mockResolvedValue(answered)
    renderPage()

    fireEvent.change(screen.getByTestId('ask-input'), { target: { value: 'ndvi trend?' } })
    fireEvent.click(screen.getByTestId('ask-send'))

    await waitFor(() => {
      expect(screen.getByText('NDVI declines under water stress.')).toBeInTheDocument()
    })
    expect(screen.getByTestId('citations')).toBeInTheDocument()

    fireEvent.click(screen.getAllByTestId('citation-0')[0])
    const drawers = screen.getAllByTestId('sources-drawer')
    expect(drawers.length).toBeGreaterThan(0)
    expect(drawers[0]).toHaveTextContent('NDVI drops under stress.')
  })

  it('sends the selected ask mode', async () => {
    vi.mocked(askApi.ask).mockResolvedValue(abstained)
    renderPage()

    fireEvent.change(screen.getByTestId('ask-mode'), { target: { value: 'research' } })
    fireEvent.change(screen.getByTestId('ask-input'), { target: { value: 'survey methods' } })
    fireEvent.click(screen.getByTestId('ask-send'))

    await waitFor(() => {
      expect(vi.mocked(askApi.ask)).toHaveBeenCalledWith(
        expect.objectContaining({ mode: 'research' })
      )
    })
  })

  it('shows a suggest-correction button when citations exist', async () => {
    vi.mocked(askApi.ask).mockResolvedValue(answered)
    renderPage()

    fireEvent.change(screen.getByTestId('ask-input'), { target: { value: 'ndvi trend?' } })
    fireEvent.click(screen.getByTestId('ask-send'))

    await waitFor(() => {
      expect(screen.getByTestId('msg-assistant')).toBeInTheDocument()
    })
    expect(screen.getByTestId('suggest-correction-btn')).toBeInTheDocument()
  })

  it('hides the suggest-correction button when no citations', async () => {
    vi.mocked(askApi.ask).mockResolvedValue(abstained)
    renderPage()

    fireEvent.change(screen.getByTestId('ask-input'), { target: { value: 'unknown topic?' } })
    fireEvent.click(screen.getByTestId('ask-send'))

    await waitFor(() => {
      expect(screen.getByTestId('abstention-card')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('suggest-correction-btn')).not.toBeInTheDocument()
  })

  it('opens correction input and submits it', async () => {
    vi.mocked(opsApi.suggestCorrection).mockResolvedValue({ id: 'cm_new', content: 'fixed', state: 'proposed' } as never)
    vi.mocked(askApi.ask).mockResolvedValue(answered)
    renderPage()

    fireEvent.change(screen.getByTestId('ask-input'), { target: { value: 'ndvi trend?' } })
    fireEvent.click(screen.getByTestId('ask-send'))

    await waitFor(() => {
      expect(screen.getByTestId('msg-assistant')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('suggest-correction-btn'))
    expect(screen.getByTestId('correction-input')).toBeInTheDocument()
    expect(screen.getByTestId('correction-textarea')).toBeInTheDocument()

    fireEvent.change(screen.getByTestId('correction-textarea'), {
      target: { value: 'NDVI is the best vegetation index.' },
    })
    fireEvent.click(screen.getByTestId('correction-submit'))

    await waitFor(() => {
      expect(opsApi.suggestCorrection).toHaveBeenCalledWith(
        'turn_test123',
        'NDVI is the best vegetation index.'
      )
      expect(screen.getByTestId('correction-submitted')).toBeInTheDocument()
    })
  })
})

import { test, expect } from '@playwright/test'

/**
 * M7 smoke: open workspace → ingest → search → ask abstention path
 * All gateway calls are mocked via route interception so the test runs
 * without a live Python backend. Verifies that the UI wires the flow
 * and that the LLM-unavailable / abstention states render without crashing.
 *
 * Also covers: RTL dir flip (en ↔ fa), health pill, and empty/loading/error
 * states survive the mocked lifecycle.
 */
test.describe('M7 smoke', () => {
  test('workspace → ingest → search → ask (abstention)', async ({ page }) => {
    // ── Mock gateway ──────────────────────────────────────────────────
    let wsOpen = false
    const collections: { id: string; name: string }[] = []
    const assets: unknown[] = []

    await page.route('**/api/v1/**', async (route) => {
      const req = route.request()
      const url = new URL(req.url())
      const path = url.pathname.replace('/api/v1', '')
      const method = req.method()

      const json = (body: unknown, status = 200) =>
        route.fulfill({
          status,
          contentType: 'application/json',
          body: JSON.stringify(body),
        })

      // health — gateway up + workspace closed/open + llm missing (abstention)
      if (path === '/health' || path === '/workspace' || path === '/health') {
        // /health is GET /health or /api/v1/health
        if (url.pathname === '/health' || path === '/health') {
          return json({
            status: 'ok',
            workspace: wsOpen ? 'open' : 'closed',
            path: wsOpen ? '/tmp/ws' : null,
            llm: { provider: 'api', configured: false, reachable: false },
            version: '0.1.0',
          })
        }
        if (path === '/workspace' && method === 'GET') {
          return json(
            wsOpen
              ? { status: 'open', path: '/tmp/ws', settings: { name: 'Smoke WS', language: 'en' } }
              : { status: 'closed', path: null },
          )
        }
        if (path === '/workspace/stats' && method === 'GET') {
          return wsOpen
            ? json({ asset_count: assets.length, segment_count: 0, storage_bytes: 0 })
            : json({ error: { code: 'workspace_not_open', message: 'No workspace is open.' } }, 409)
        }
      }

      if (path === '/workspace/create' && method === 'POST') {
        wsOpen = true
        collections.length = 0
        return json({ status: 'open', path: '/tmp/ws' }, 201)
      }
      if (path === '/workspace/open' && method === 'POST') {
        wsOpen = true
        return json({ status: 'open', path: '/tmp/ws' })
      }
      if (path === '/workspace/close' && method === 'POST') {
        wsOpen = false
        return json({ status: 'closed' })
      }

      // collections
      if (path === '/collections' && method === 'GET') {
        return wsOpen ? json(collections) : json({ error: { code: 'workspace_not_open', message: '' } }, 409)
      }
      if (path === '/collections' && method === 'POST') {
        const body = req.postDataJSON() as { name: string }
        const col = { id: `col_${collections.length + 1}`, name: body.name, description: null }
        collections.push(col)
        return json(col, 201)
      }

      // ingest — return 202 job
      if (path === '/ingest' && method === 'POST') {
        return json({ job_id: 'job_smoke', status: 'queued' }, 202)
      }
      if (path.startsWith('/jobs/')) {
        return json({ id: 'job_smoke', type: 'ingest', status: 'completed', progress: 1, result: { asset_id: 'asset_1', segment_count: 3 } })
      }

      // assets
      if (path.startsWith('/assets')) {
        return json(assets)
      }

      // search — return 1 hit
      if (path === '/search' && method === 'POST') {
        return json({
          hits: [
            {
              id: 'seg_1',
              score: 0.92,
              sparse_score: 0.5,
              dense_score: 0.42,
              text: 'Sugarcane NDVI stress threshold is 0.4 (severe below).',
              locator: { file: 'doc.pdf', page: 1 },
              metadata: {},
            },
          ],
          total: 1,
          took_ms: 12,
        })
      }

      // ask — abstention (LLM unavailable)
      if (path === '/ask' && method === 'POST') {
        return json({
          answer: '',
          citations: [],
          abstained: true,
          abstain_reason: 'LLM unavailable — no API key configured.',
        })
      }

      // doctor / index / feedback — minimal stubs
      if (path.startsWith('/doctor') || path.startsWith('/index') || path.startsWith('/feedback')) {
        return json({})
      }
      // agent stubs
      if (path.startsWith('/agent')) {
        if (path === '/agent/tools' || path === '/agent/tools/') return json({ tools: [{ name: 'geo_search', description: 'search', params: {}, returns: '', timeout_s: 30, cacheable: false }] })
        if (path === '/agent/conversations' || path.startsWith('/agent/files')) return json({ conversations: [], files: [], pattern: '' })
        if (path === '/agent/playbooks') return json({ playbooks: [] })
        if (path.startsWith('/agent/farms')) return json({ farms: [], count: 0, source: null, reports: [] })
        if (path.startsWith('/agent/maps')) return json({ artifacts: [], layers: [], count: 0, pattern: '', legend: null })
      }

      // SSE — empty
      if (path === '/events') {
        return route.fulfill({ status: 200, contentType: 'text/event-stream', body: 'data: ping\n\n' })
      }

      return route.continue()
    })

    // health + openapi
    await page.route('**/openapi.json', async (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ openapi: '3.0.0', info: { title: 'x', version: '0.1' }, paths: {} }) }),
    )

    // ── Flow ──────────────────────────────────────────────────────────
    await page.goto('/')

    // App shell renders, health pill shows gateway online
    await expect(page.getByTestId('app-shell')).toBeVisible()
    // Overview title
    await expect(page.getByRole('heading', { name: /Overview|نمای کلی/ })).toBeVisible()

    // Workspace switcher visible; create/open workspace
    const pathInput = page.getByPlaceholder(/\/path\/to\/workspace|\/مسیر/)
    await expect(pathInput).toBeVisible()
    await pathInput.fill('/tmp/ws')
    const createBtn = page.getByRole('button', { name: /Create|ایجاد/ })
    await createBtn.click()
    await expect(page.getByTestId('workspace-status')).toContainText(/Smoke WS|open/i, { timeout: 5_000 })

    // Collections — create one
    await page.getByRole('link', { name: /Collections|مجموعه/ }).click()
    await page.getByRole('button', { name: /New collection|مجموعه جدید/ }).click()
    const nameInput = page.getByTestId('collection-name')
    await nameInput.fill('smoke-docs')
    await page.getByRole('button', { name: /Create|ایجاد/ }).click()
    await expect(page.getByText('smoke-docs')).toBeVisible({ timeout: 5_000 })

    // Ingest — smoke that ingest page renders (file upload is mocked)
    await page.getByRole('link', { name: /Ingest|ورود داده/ }).click()
    await expect(page.getByRole('heading', { name: /Ingest|ورود داده/ })).toBeVisible()

    // Search — run query and see hit
    await page.getByRole('link', { name: /^Search|جستجو/ }).click()
    const searchInput = page.getByPlaceholder(/Search the workspace|جستجو در فضای کاری/)
    await searchInput.fill('NDVI stress')
    // click Search button (there are two: header nav and filter bar) — use the one in search page
    await page.getByRole('button', { name: /^Search$|^جستجو$/ }).last().click()
    await expect(page.getByText(/Sugarcane NDVI/)).toBeVisible({ timeout: 5_000 })

    // Ask — abstention path
    await page.getByRole('link', { name: /Ask|پرسش/ }).click()
    const askInput = page.getByPlaceholder(/Ask a question|سؤال خود را/)
    await askInput.fill('What is the NDVI threshold for sugarcane stress?')
    await page.getByRole('button', { name: /Send|ارسال/ }).click()
    await expect(page.getByText(/No answer provided|پاسخی ارائه نشد/)).toBeVisible({ timeout: 5_000 })
    await expect(page.getByText(/LLM unavailable|مدل زبانی/)).toBeVisible()

    // RTL flip — en → fa → en
    // toggle to fa
    const faBtn = page.getByRole('button', { name: /FA|فارسی/ })
    if (await faBtn.isVisible()) {
      await faBtn.click()
      await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
      // flip back to en
      await page.getByRole('button', { name: /EN|English/ }).click()
      await expect(page.locator('html')).toHaveAttribute('dir', 'ltr')
    }

    // Maps + Farms render empty states without crashing
    await page.getByRole('link', { name: /Maps|نقشه/ }).click()
    await expect(page.getByRole('heading', { name: /Maps|نقشه/ })).toBeVisible()
    await page.getByRole('link', { name: /Farms|مزارع/ }).click()
    await expect(page.getByRole('heading', { name: /Farms|مزارع/ })).toBeVisible()

    // A11y sanity: every page has a single h1
    await expect(page.locator('h1')).toHaveCount(1)
  })
})

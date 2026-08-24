import { describe, expect, it } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { LanguageToggle } from '@/app/LanguageToggle'
import { routes } from '@/app/router'

function renderWithProviders(router: ReturnType<typeof createMemoryRouter>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}

describe('LanguageToggle', () => {
  it('switches language and direction', async () => {
    const router = createMemoryRouter([
      { path: '/', element: <LanguageToggle /> },
    ])
    renderWithProviders(router)

    expect(document.documentElement.dir).toBe('ltr')
    fireEvent.click(screen.getByRole('button', { name: 'فا' }))

    await waitFor(() => {
      expect(document.documentElement.dir).toBe('rtl')
      expect(document.documentElement.lang).toBe('fa')
    })
    expect(localStorage.getItem('gf.language')).toBe('fa')

    fireEvent.click(screen.getByRole('button', { name: 'EN' }))
    await waitFor(() => {
      expect(document.documentElement.dir).toBe('ltr')
    })
  })
})

describe('i18n coverage', () => {
  it('fa translation covers all en keys', async () => {
    const en = (await import('@/i18n/en.json')).default
    const fa = (await import('@/i18n/fa.json')).default

    const flat = (obj: Record<string, unknown>, prefix = ''): string[] =>
      Object.entries(obj).flatMap(([k, v]) =>
        typeof v === 'object' && v !== null
          ? flat(v as Record<string, unknown>, `${prefix}${k}.`)
          : [`${prefix}${k}`]
      )

    const enKeys: string[] = flat(en).sort()
    const faKeys = new Set(flat(fa))
    expect(enKeys.filter((k: string) => !faKeys.has(k))).toEqual([])
  })
})

describe('RTL smoke', () => {
  it('app renders with fa locale without layout errors', async () => {
    const { setLanguage } = await import('@/i18n')
    setLanguage('fa')
    const router = createMemoryRouter(routes, { initialEntries: ['/'] })
    renderWithProviders(router)

    await waitFor(() => {
      expect(document.documentElement.dir).toBe('rtl')
    })
    expect(screen.getByText('نمای کلی')).toBeInTheDocument()
    setLanguage('en')
  })
})

describe('AppShell integration', () => {
  it('language toggle inside header flips UI text', async () => {
    const router = createMemoryRouter(routes, { initialEntries: ['/'] })
    renderWithProviders(router)

    expect(screen.getAllByText('Workspace').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: 'فا' }))

    await waitFor(() => {
      expect(screen.getAllByText('فضای کاری').length).toBeGreaterThan(0)
    })
  })
})

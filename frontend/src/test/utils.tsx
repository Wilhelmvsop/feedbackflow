import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { AuthProvider } from '../lib/auth'
import { ToastProvider } from '../lib/toast'

export function renderWithProviders(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AuthProvider>{ui}</AuthProvider>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

type Route = { method?: string; path: string | RegExp; status?: number; body?: unknown }

/** Minimal fetch fake: first matching route wins; records every call. */
export function mockFetch(routes: Route[]) {
  const calls: { method: string; url: string; body: unknown; headers: Record<string, string> }[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input)
    const method = init.method ?? 'GET'
    calls.push({ method, url, body: init.body ? JSON.parse(String(init.body)) : undefined, headers: (init.headers ?? {}) as Record<string, string> })
    const route = routes.find(r => (r.method ?? 'GET') === method && (typeof r.path === 'string' ? url === r.path : r.path.test(url)))
    if (!route) return new Response(JSON.stringify({ detail: `No mock for ${method} ${url}` }), { status: 500 })
    return new Response(route.status === 204 ? null : JSON.stringify(route.body ?? {}), { status: route.status ?? 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

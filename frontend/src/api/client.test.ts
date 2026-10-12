import { mockFetch } from '../test/utils'
import { ApiError, request, setAuthToken, setUnauthorizedHandler } from './client'

describe('api client', () => {
  afterEach(() => {
    setAuthToken(null)
    setUnauthorizedHandler(null)
  })

  it('sends the bearer token and JSON body', async () => {
    const calls = mockFetch([{ method: 'POST', path: '/api/things', body: { ok: true } }])
    setAuthToken('secret')
    await expect(request('/things', { method: 'POST', body: { a: 1 } })).resolves.toEqual({ ok: true })
    expect(calls[0].headers).toMatchObject({ Authorization: 'Bearer secret', 'Content-Type': 'application/json' })
    expect(calls[0].body).toEqual({ a: 1 })
  })

  it('surfaces FastAPI error details', async () => {
    mockFetch([
      { path: '/api/conflict', status: 409, body: { detail: 'Only failed analyses can be retried' } },
      { path: '/api/invalid', status: 422, body: { detail: [{ loc: ['body', 'title'], msg: 'Field required' }] } },
    ])
    await expect(request('/conflict')).rejects.toEqual(new ApiError(409, 'Only failed analyses can be retried'))
    await expect(request('/invalid')).rejects.toThrow('Field required')
  })

  it('reports an expired session once per 401', async () => {
    mockFetch([{ path: '/api/feedback', status: 401, body: { detail: 'Your session has expired' } }])
    const onUnauthorized = vi.fn()
    setAuthToken('stale')
    setUnauthorizedHandler(onUnauthorized)
    await expect(request('/feedback')).rejects.toMatchObject({ status: 401 })
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })

  it('maps network failures to a readable error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(request('/feedback')).rejects.toMatchObject({ status: 0, message: expect.stringContaining('Cannot reach') })
  })
})

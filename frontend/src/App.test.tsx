import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { mockFetch, renderWithProviders } from './test/utils'
import type { Feedback, Session } from './types'

const session: Session = {
  token: 'tok', expires_at: '2999-01-01T00:00:00Z', email: 'demo@feedbackflow.local',
  workspace: { id: 1, slug: 'demo', name: 'Acme Product Team' },
}

const feedback = (id: number, message: string): Feedback => ({
  id, message, category: 'bug', page_path: '/import', status: 'new', tags: '', assignee: null,
  created_at: new Date().toISOString(), requirement_id: null, analysis: null,
})

const stats = { total: 2, new: 2, triaged: 0, in_progress: 0, resolved: 0 }

describe('App', () => {
  beforeEach(() => { window.location.hash = '' })

  it('signs in and loads the inbox', async () => {
    const calls = mockFetch([
      { method: 'POST', path: '/api/auth/login', body: session },
      { path: /\/api\/feedback\?/, body: { items: [feedback(1, 'Upload is slow'), feedback(2, 'Export to CSV')], total: 2, page: 1, page_size: 20 } },
      { path: '/api/feedback/stats', body: stats },
      { path: '/api/requirements', body: [] },
    ])
    renderWithProviders(<App />)

    await userEvent.clear(screen.getByLabelText('Password'))
    await userEvent.type(screen.getByLabelText('Password'), 'pw')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByText('Upload is slow')).toBeInTheDocument()
    expect(screen.getByText('Acme Product Team')).toBeInTheDocument()
    expect(calls[0].body).toEqual({ email: 'demo@feedbackflow.local', password: 'pw' })
    expect(JSON.parse(localStorage.getItem('ff-session')!).token).toBe('tok')
  })

  it('shows the login error from the API', async () => {
    mockFetch([{ method: 'POST', path: '/api/auth/login', status: 401, body: { detail: 'Email or password is incorrect' } }])
    renderWithProviders(<App />)
    await userEvent.type(screen.getByLabelText('Password'), 'x')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Email or password is incorrect')
  })

  it('returns to the login page when the stored session has expired server-side', async () => {
    localStorage.setItem('ff-session', JSON.stringify(session))
    mockFetch([
      { path: /\/api\/feedback/, status: 401, body: { detail: 'Your session has expired' } },
      { path: '/api/requirements', status: 401, body: { detail: 'Your session has expired' } },
    ])
    renderWithProviders(<App />)
    expect(await screen.findByRole('button', { name: /sign in/i })).toBeInTheDocument()
    expect(localStorage.getItem('ff-session')).toBeNull()
  })

  it('applies a bulk status change to selected rows', async () => {
    localStorage.setItem('ff-session', JSON.stringify(session))
    const calls = mockFetch([
      { path: /\/api\/feedback\?/, body: { items: [feedback(1, 'Upload is slow'), feedback(2, 'Export to CSV')], total: 2, page: 1, page_size: 20 } },
      { path: '/api/feedback/stats', body: stats },
      { path: '/api/requirements', body: [] },
      { method: 'POST', path: '/api/feedback/bulk', body: { updated: 1 } },
    ])
    renderWithProviders(<App />)

    await userEvent.click(await screen.findByLabelText('Select FB-001'))
    await userEvent.selectOptions(screen.getByLabelText('Set status for selected feedback'), 'triaged')

    await waitFor(() => expect(calls.find(c => c.url === '/api/feedback/bulk')?.body).toEqual({ ids: [1], status: 'triaged' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Updated 1 feedback item.')
    expect(within(screen.getByRole('table')).getByLabelText('Select FB-001')).not.toBeChecked()
  })
})

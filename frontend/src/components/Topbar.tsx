import type { View } from './Sidebar'
import { feedbackRef, initials } from '../lib/format'

export function Topbar({ view, feedbackId, email }: { view: View; feedbackId: number | null; email: string }) {
  return (
    <header className="topbar">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <span>Workspace</span><span className="slash">/</span><strong>{view === 'feedback' ? 'Inbox' : 'Requirements'}</strong>
        {view === 'feedback' && feedbackId !== null && <><span className="slash">/</span><strong className="crumb-active">{feedbackRef(feedbackId)}</strong></>}
      </nav>
      <div className="top-actions">
        <a className="help-btn" href="/docs" target="_blank" rel="noreferrer">API docs</a>
        <span className="top-divider" />
        <span className="avatar-small" title={email}>{initials(email)}</span>
      </div>
    </header>
  )
}

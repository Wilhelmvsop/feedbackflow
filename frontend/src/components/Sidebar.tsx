import { ArrowRight, ArrowUpRight, ClipboardList, Inbox, Layers2, LogOut, Settings2, Sparkles } from 'lucide-react'
import type { Session } from '../types'
import { initials } from '../lib/format'

export type View = 'feedback' | 'requirements'

type Props = {
  session: Session
  view: View
  newCount?: number
  requirementCount?: number
  onNavigate: (view: View) => void
  onOpenWidgetSetup: () => void
  onSignOut: () => void
}

export function Sidebar({ session, view, newCount, requirementCount, onNavigate, onOpenWidgetSetup, onSignOut }: Props) {
  const { workspace, email } = session
  return (
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Layers2 size={19} /></div><span>feedback<span className="brand-light">flow</span></span></div>
      <div className="workspace-switch">
        <span className="workspace-avatar">{initials(workspace.name)}</span>
        <span className="workspace-copy"><strong>{workspace.name}</strong><small>Workspace · {workspace.slug}</small></span>
      </div>
      <div className="nav-label">WORKSPACE</div>
      <nav>
        <button className={`nav-item ${view === 'feedback' ? 'active' : ''}`} aria-current={view === 'feedback' ? 'page' : undefined} onClick={() => onNavigate('feedback')}>
          <Inbox size={17} /><span>Inbox</span><span className="nav-count" title="Needs triage">{newCount ?? ''}</span>
        </button>
        <button className={`nav-item ${view === 'requirements' ? 'active' : ''}`} aria-current={view === 'requirements' ? 'page' : undefined} onClick={() => onNavigate('requirements')}>
          <ClipboardList size={17} /><span>Requirements</span><span className="nav-count">{requirementCount ?? ''}</span>
        </button>
      </nav>
      <div className="nav-label nav-label-gap">MANAGE</div>
      <button className="nav-item muted-nav" onClick={onOpenWidgetSetup}><Settings2 size={17} /><span>Widget setup</span><ArrowUpRight className="nav-end" size={14} /></button>
      <div className="sidebar-spacer" />
      <div className="side-tip">
        <div className="tip-icon"><Sparkles size={15} /></div>
        <strong>Good feedback<br />makes good products.</strong>
        <p>Turn the small signals into your next big improvement.</p>
        <button onClick={() => onNavigate('requirements')}>See requirements <ArrowRight size={13} /></button>
      </div>
      <button className="profile" onClick={onSignOut} title="Sign out">
        <span className="profile-avatar">{initials(email)}</span>
        <span className="profile-copy"><strong>{email.split('@')[0]}</strong><small>{email}</small></span>
        <LogOut size={15} aria-label="Sign out" />
      </button>
    </aside>
  )
}

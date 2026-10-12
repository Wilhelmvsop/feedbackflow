import { ArrowRight, ClipboardList, FileText, MessageSquare } from 'lucide-react'
import type { Requirement } from '../types'
import { requirementRef } from '../lib/format'

type Props = { requirements: Requirement[] | undefined; selectedId: number | null; onSelect: (id: number) => void; onBackToInbox: () => void }

export function RequirementsView({ requirements, selectedId, onSelect, onBackToInbox }: Props) {
  const count = requirements?.length ?? 0
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">THE WORK TAKING SHAPE</p>
          <h1>Requirements <span className="heading-count">{count}</span></h1>
          <p className="muted">Human-reviewed plans, always grounded in what users told you.</p>
        </div>
      </div>
      <section className="feedback-panel requirements-panel">
        <div className="panel-heading"><div><h2>Requirement drafts <span>{count}</span></h2><p>Review AI-assisted drafts and confirm what your team will build.</p></div></div>
        {!requirements ? (
          <div className="empty-state"><span className="spinner" /><p>Loading requirements…</p></div>
        ) : count ? (
          <div className="requirement-list">
            {requirements.map(req => (
              <button className={`requirement-card ${selectedId === req.id ? 'req-selected' : ''}`} key={req.id} onClick={() => onSelect(req.id)}>
                <div className="requirement-card-icon"><FileText size={18} /></div>
                <div className="requirement-card-content">
                  <div className="requirement-meta"><span className={`req-status req-${req.status}`}>{req.status}</span><span>{requirementRef(req.id)}</span><span>{req.tasks.filter(t => t.done).length}/{req.tasks.length} tasks</span></div>
                  <strong>{req.title}</strong>
                  <p>{req.problem}</p>
                  <small><MessageSquare size={13} /> From feedback #{req.source_feedback_ids.join(', #')}</small>
                </div>
                <ArrowRight size={16} />
              </button>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <div className="empty-icon"><ClipboardList size={22} /></div>
            <strong>No requirement drafts yet</strong>
            <p>Open a feedback item and ask AI for a first draft.</p>
            <button className="text-button" onClick={onBackToInbox}>Back to inbox</button>
          </div>
        )}
      </section>
    </>
  )
}

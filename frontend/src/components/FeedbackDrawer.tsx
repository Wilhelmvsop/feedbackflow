import { useState } from 'react'
import { ArrowRight, Check, CheckCheck, FileText, Sparkles, X } from 'lucide-react'
import { useCreateRequirement, useFeedback, useStartAnalysis, useUpdateFeedback } from '../api/queries'
import { useToast } from '../lib/toast'
import { errorMessage, feedbackRef, statusLabel } from '../lib/format'
import { FEEDBACK_STATUSES, type Feedback, type FeedbackPatch, type FeedbackStatus } from '../types'
import { useEscape } from './useEscape'

type Props = { feedbackId: number; onClose: () => void; onOpenRequirement: (id: number) => void }

export function FeedbackDrawer({ feedbackId, onClose, onOpenRequirement }: Props) {
  const { data: item, error } = useFeedback(feedbackId)
  useEscape(onClose)

  return (
    <>
      <button className="drawer-scrim" aria-label="Close detail" onClick={onClose} />
      <aside className="detail-drawer" aria-label="Feedback detail">
        <div className="drawer-top">
          <div><span className="detail-id">FEEDBACK · {feedbackRef(feedbackId)}</span><button className="drawer-close" onClick={onClose} aria-label="Close"><X size={18} /></button></div>
          <h2>Feedback detail</h2>
        </div>
        {item
          ? <FeedbackDetail key={item.id} item={item} onOpenRequirement={onOpenRequirement} />
          : <div className="drawer-scroll"><div className="analysis-loading">{error ? errorMessage(error) : <><span className="spinner" /> Loading…</>}</div></div>}
        <div className="drawer-bottom"><span><Check size={14} /> Changes saved automatically</span><button onClick={onClose}>Done</button></div>
      </aside>
    </>
  )
}

function FeedbackDetail({ item, onOpenRequirement }: { item: Feedback; onOpenRequirement: (id: number) => void }) {
  const notify = useToast()
  const update = useUpdateFeedback()
  const startAnalysis = useStartAnalysis()
  const createRequirement = useCreateRequirement()
  const [tags, setTags] = useState(item.tags)
  const [assignee, setAssignee] = useState(item.assignee ?? '')

  const save = (patch: FeedbackPatch) => update.mutate({ id: item.id, patch }, { onError: e => notify(errorMessage(e)) })
  const analysis = item.analysis
  const failed = analysis?.status === 'failed'
  const running = analysis?.status === 'queued' || analysis?.status === 'running'
  const result = analysis?.status === 'succeeded' ? analysis.result : null

  const analyze = () => startAnalysis.mutate({ id: item.id, retry: failed }, { onError: e => notify(errorMessage(e)) })
  const draft = () => {
    if (item.requirement_id) return onOpenRequirement(item.requirement_id)
    createRequirement.mutate(item.id, { onSuccess: req => onOpenRequirement(req.id), onError: e => notify(errorMessage(e)) })
  }

  return (
    <div className="drawer-scroll">
      <div className="detail-status-row">
        <span className={`status status-${item.status}`}><i />{statusLabel(item.status)}</span>
        <select aria-label="Feedback status" value={item.status} onChange={e => save({ status: e.target.value as FeedbackStatus })}>
          {FEEDBACK_STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
      </div>
      <blockquote>“{item.message}”</blockquote>
      <div className="detail-meta">
        <div><span>RECEIVED</span><strong>{new Date(item.created_at).toLocaleString()}</strong></div>
        <div><span>CATEGORY</span><strong>{item.category}</strong></div>
        {item.page_path && <div><span>PAGE</span><strong>{item.page_path}</strong></div>}
      </div>
      <label className="field-label">TAGS<input className="detail-input" value={tags} maxLength={500} onChange={e => setTags(e.target.value)} onBlur={() => tags !== item.tags && save({ tags })} placeholder="Add tags separated by commas" /></label>
      <label className="field-label">ASSIGNEE<input className="detail-input" value={assignee} maxLength={254} onChange={e => setAssignee(e.target.value)} onBlur={() => assignee !== (item.assignee ?? '') && save({ assignee: assignee.trim() || null })} placeholder="Assign a teammate" /></label>
      <div className="detail-divider" />

      <div className="ai-heading">
        <div className="ai-badge"><Sparkles size={15} /></div>
        <div><strong>AI first pass</strong><small>Grounded in this feedback{analysis ? ` · v${analysis.version}` : ''}</small></div>
      </div>
      {running ? (
        <div className="analysis-loading" role="status"><span className="spinner" /> Thinking through the details…</div>
      ) : !result ? (
        <div className="analysis-empty">
          <p>{failed ? analysis?.error : 'Get a structured first pass: the problem, what is missing, and a draft your team can review.'}</p>
          <button className="primary" onClick={analyze} disabled={startAnalysis.isPending}><Sparkles size={15} />{failed ? 'Retry analysis' : 'Generate requirement draft'}</button>
        </div>
      ) : (
        <>
          <div className="analysis-result">
            <span className="analysis-label">SUGGESTED DIRECTION</span>
            <strong>{result.suggested_title}</strong>
            <p>{result.problem}</p>
            <span className="analysis-label">STILL TO CLARIFY</span>
            <ul>{result.open_questions.map(q => <li key={q}>{q}</li>)}</ul>
            <span className="analysis-label">ACCEPTANCE CRITERIA</span>
            <ul>{result.acceptance_criteria.map(c => <li key={c}>{c}</li>)}</ul>
            {result.related_feedback.length > 0 && (
              <>
                <span className="analysis-label">POSSIBLE RELATED FEEDBACK</span>
                <ul>{result.related_feedback.map(match => <li key={match.id}><strong>#{match.id} · {match.reason}</strong><br />{match.message}</li>)}</ul>
              </>
            )}
            <p className="source-note"><CheckCheck size={14} /> Source: feedback #{item.id}</p>
          </div>
          <button className="primary wide draft-button" onClick={draft} disabled={createRequirement.isPending}>
            <FileText size={15} /> {item.requirement_id ? 'Open linked requirement' : 'Create linked requirement draft'} <ArrowRight size={15} />
          </button>
        </>
      )}
    </div>
  )
}
